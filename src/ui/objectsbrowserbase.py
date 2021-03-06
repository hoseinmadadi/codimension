#
# -*- coding: utf-8 -*-
#
# codimension - graphics python two-way code editor and analyzer
# Copyright (C) 2010  Sergey Satskiy <sergey.satskiy@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# $Id$
#


" Base and auxiliary classes for G/F/C browsers "


import os
from PyQt4.QtCore    import Qt, QModelIndex, SIGNAL, QRegExp, pyqtSignal
from PyQt4.QtGui     import QAbstractItemView, QApplication, \
                            QSortFilterProxyModel, QTreeView
from utils.globals   import GlobalData
from utils.project   import CodimensionProject
from viewitems       import DirectoryItemType, \
                            SysPathItemType, GlobalsItemType, ImportsItemType, \
                            FunctionsItemType, ClassesItemType, \
                            StaticAttributesItemType, InstanceAttributesItemType, \
                            FunctionItemType, ClassItemType
from itemdelegates   import NoOutlineHeightDelegate
from utils.fileutils import detectFileType, PythonFileType, Python3FileType



class ObjectsBrowserSortFilterProxyModel( QSortFilterProxyModel ):
    """
    Objects (globals, functions, classes) browser sort filter proxy model
    implementation. It allows filtering basing on top level items.
    """

    def __init__( self, parent = None ):
        QSortFilterProxyModel.__init__( self, parent )
        self.__sortColumn = None    # Avoid pylint complains
        self.__sortOrder = None     # Avoid pylint complains

        self.__filters = []
        self.__filtersCount = 0
        self.__sourceModelRoot = None
        return

    def sort( self, column, order ):
        " Sorts the items "
        self.__sortColumn = column
        self.__sortOrder = order
        QSortFilterProxyModel.sort( self, column, order )
        return

    def lessThan( self, left, right ):
        " Sorts the displayed items "
        lmodel = left.model()
        lhs = lmodel and lmodel.item( left ) or None
        if lhs:
            rmodel = right.model()
            rhs = rmodel and rmodel.item( right ) or None
            if rhs:
                return lhs.lessThan( rhs, self.__sortColumn, self.__sortOrder )
        return False

    def item( self, index ):
        " Provides a reference to the item "
        if not index.isValid():
            return None

        sourceIndex = self.mapToSource( index )
        return self.sourceModel().item( sourceIndex )

    def hasChildren( self, parent = QModelIndex() ):
        " Checks the presence of the child items "
        sourceIndex = self.mapToSource( parent )
        return self.sourceModel().hasChildren( sourceIndex )

    def setFilter( self, text ):
        " Sets the new filters "
        self.__filters = []
        self.__filtersCount = 0
        self.__sourceModelRoot = None
        for part in str( text ).strip().split():
            regexp = QRegExp( part, Qt.CaseInsensitive, QRegExp.RegExp2 )
            self.__filters.append( regexp )
            self.__filtersCount += 1
        self.__sourceModelRoot = self.sourceModel().rootItem
        return

    def filterAcceptsRow( self, sourceRow, sourceParent ):
        " Filters rows "

        if self.__filtersCount == 0 or self.__sourceModelRoot is None:
            return True     # No filters

        sindex = self.sourceModel().index( sourceRow, 0, sourceParent )
        if not sindex.isValid():
            return False

        sitem = self.sourceModel().item( sindex )
        if not sitem is None:
            parent = sitem.parent()
            if not parent is None:
                if parent.parentItem is None:
                    # Filter top level items only
                    nameToMatch = sitem.sourceObj.name
                    for regexp in self.__filters:
                        if regexp.indexIn( nameToMatch ) == -1:
                            return False

        # Show all the nested items
        return True



class ObjectsBrowser( QTreeView ):
    " Common functionality of the G/F/C browsers "

    openingItem = pyqtSignal( str, int )

    def __init__( self, sourceModel, parent = None ):
        QTreeView.__init__( self, parent )

        self.__model = sourceModel
        self.__sortModel = ObjectsBrowserSortFilterProxyModel()
        self.__sortModel.setDynamicSortFilter( True )
        self.__sortModel.setSourceModel( self.__model )
        self.setModel( self.__sortModel )
        self.contextItem = None

        self.connect( self, SIGNAL( "activated(const QModelIndex &)" ),
                      self._openItem )
        self.connect( self, SIGNAL( "expanded(const QModelIndex &)" ),
                      self._resizeColumns )
        self.connect( self, SIGNAL( "collapsed(const QModelIndex &)" ),
                      self._resizeColumns )
        GlobalData().project.fsChanged.connect( self.onFSChanged )
        self.connect( self.__model, SIGNAL( 'modelReset()' ),
                      self.updateCounter )

        self.setRootIsDecorated( True )
        self.setAlternatingRowColors( True )
        self.setUniformRowHeights( True )
        self.setItemDelegate( NoOutlineHeightDelegate( 4 ) )

        header = self.header()
        header.setSortIndicator( 0, Qt.AscendingOrder )
        header.setSortIndicatorShown( True )
        header.setClickable( True )

        self.setSortingEnabled( True )

        self.setSelectionMode( QAbstractItemView.SingleSelection )
        self.setSelectionBehavior( QAbstractItemView.SelectRows )

        self.layoutDisplay()

        GlobalData().project.projectChanged.connect( self.__onProjectChanged )
        return

    def updateCounter( self, parent = None, start = 0, end = 0 ):
        " Updates the header with the info of currently visible and total items "
        text = "Name (" + str( self.model().rowCount() ) + " of " + \
                          str( self.__model.totalRowCount() ) + ")"
        self.__model.updateRootData( 0, text )
        return

    def __onProjectChanged( self, what ):
        " Triggered when a project is changed "

        if what == CodimensionProject.CompleteProject:
            self.__model.reset()
            self.layoutDisplay()
            self.updateCounter()
        return

    def setFilter( self, text ):
        " Sets the new filter for items "

        # Notify the filtering model of the new filters
        self.model().setFilter( text )

        # This is to trigger filtering - ugly but I don't know how else
        self.model().setFilterRegExp( "" )

        # No need to resort but need to resize columns
        self.doItemsLayout()
        self._resizeColumns( QModelIndex() )
        return

    def layoutDisplay( self ):
        " Performs the layout operation "
        self.doItemsLayout()
        self._resizeColumns( QModelIndex() )
        self._resort()
        return

    def _resizeColumns( self, index ):
        " Resizes the view when items get expanded or collapsed "

        rowCount = self.model().rowCount()
        columnCount = self.model().columnCount()
        self.header().setStretchLastSection( rowCount == 0 )

        index = 0
        while index < columnCount - 1:
            width = max( 100, self.sizeHintForColumn( index ) )
            self.header().resizeSection( index, width )
            index += 1

        # The last column is 'Line' so it should be narrower
        width = max( 40, self.sizeHintForColumn( index ) )
        self.header().resizeSection( index, width )
        return

    def _resort( self ):
        " Re-sorts the tree "
        self.model().sort( self.header().sortIndicatorSection(),
                           self.header().sortIndicatorOrder() )
        return

    def mouseDoubleClickEvent( self, mouseEvent ):
        """
        Reimplemented to disable expanding/collapsing of items when
        double-clicking. Instead the double-clicked entry is opened.
        """

        index = self.indexAt( mouseEvent.pos() )
        if not index.isValid():
            return

        item = self.model().item( index )
        if item.itemType in [ GlobalsItemType,
                              ImportsItemType, FunctionsItemType,
                              ClassesItemType, StaticAttributesItemType,
                              InstanceAttributesItemType,
                              DirectoryItemType, SysPathItemType ]:
            # This will return the first column index regardless in what
            # column the double click happened
            index = self.selectedIndexes()[ 0 ]
            if self.isExpanded( index ):
                self.collapse( index )
            else:
                self.expand( index )
        else:
            self.openItem( item )
        return

    def _openItem( self ):
        " Triggers when an item is clicked or double clicked "
        item = self.model().item( self.selectedIndexes()[ 0 ] )
        self.openItem( item )
        return

    def openItem( self, item ):
        " Handles the case when an item is activated "
        if item.itemType in [ GlobalsItemType,
                              ImportsItemType, FunctionsItemType,
                              ClassesItemType, StaticAttributesItemType,
                              InstanceAttributesItemType,
                              DirectoryItemType, SysPathItemType ]:
            return
        path = item.getPath()
        line = item.data( 2 )
        self.openingItem.emit( str( path ), line )
        GlobalData().mainWindow.openFile( path, line )
        return

    def getDisassembled( self, item ):
        " Handles showing disassembled code "
        if item.itemType not in [ FunctionItemType, ClassItemType ]:
            return

        path = item.getPath()
        qualifiedName = item.getQualifiedName()
        GlobalData().mainWindow.showDisassembler( path, qualifiedName )
        return

    def copyToClipboard( self ):
        " Copies the path to the file where the element is to the clipboard "
        item = self.model().item( self.currentIndex() )
        QApplication.clipboard().setText( item.getPath() )
        return

    def onFileUpdated( self, fileName ):
        " Triggered when the file is updated "

        if not GlobalData().project.isProjectFile( fileName ):
            # Not a project file
            return

        if detectFileType( fileName ) not in [ PythonFileType,
                                               Python3FileType ]:
            return

        if self.__model.onFileUpdated( fileName ):
            # Need resort and counter updates
            self.layoutDisplay()
            self.updateCounter()
            self.model().setFilterRegExp( "" )
        return

    def onFSChanged( self, items ):
        " Triggered when filesystem has changes "
        addedPythonFiles = []
        deletedPythonFiles = []

        for path in items:
            path = str( path )
            if path.endswith( os.path.sep ):
                continue    # dirs are out of interest
            if path.startswith( '+' ):
                path = path[ 1: ]
                if detectFileType( path ) not in [ PythonFileType,
                                                   Python3FileType ]:
                    continue
                addedPythonFiles.append( path )
            else:
                path = path[ 1: ]
                if detectFileType( path ) not in [ PythonFileType,
                                                   Python3FileType ]:
                    continue
                deletedPythonFiles.append( path )
        if addedPythonFiles or deletedPythonFiles:
            if self.__model.onFSChanged( addedPythonFiles,
                                         deletedPythonFiles ):
                # Need resort and counter updates
                self.layoutDisplay()
                self.updateCounter()
                self.model().setFilterRegExp( "" )
                self.emit( SIGNAL( 'modelFilesChanged' ) )
        return

    def selectionChanged( self, selected, deselected ):
        " Slot is called when the selection has been changed "
        if selected.indexes():
            # The objects browsers may have no more than one selected item
            self.emit( SIGNAL( "selectionChanged" ),
                       selected.indexes()[ 0 ] )
        else:
            self.emit( SIGNAL( "selectionChanged" ), None )
        QTreeView.selectionChanged( self, selected, deselected )
        return

