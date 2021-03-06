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

""" Diff viewer tab widget """


from PyQt4.QtCore import Qt, QEvent, pyqtSignal
from PyQt4.QtGui import QApplication
from ui.mainwindowtabwidgetbase import MainWindowTabWidgetBase
from utils.settings import Settings
from htmltabwidget import HTMLTabWidget


class DiffTabWidget( HTMLTabWidget ):
    " The widget which displays a RO diff page "

    textEditorZoom = pyqtSignal( int )

    def __init__( self, parent = None ):
        HTMLTabWidget.__init__( self, parent )
        self.installEventFilter( self )
        return

    def eventFilter( self, obj, event ):
        " Event filter to catch shortcuts on UBUNTU "
        if event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            if modifiers == Qt.ControlModifier:
                if key == Qt.Key_Minus:
                    return self.onZoomOut()
                if key == Qt.Key_Equal:
                    return self.onZoomIn()
                if key == Qt.Key_0:
                    return self.onZoomReset()
            if modifiers == Qt.KeypadModifier | Qt.ControlModifier:
                if key == Qt.Key_Minus:
                    return self.onZoomOut()
                if key == Qt.Key_Plus:
                    return self.onZoomIn()
                if key == Qt.Key_0:
                    return self.onZoomReset()

        return HTMLTabWidget.eventFilter( self, obj, event )

    def wheelEvent( self, event ):
        " Mouse wheel event "
        if QApplication.keyboardModifiers() == Qt.ControlModifier:
            if event.delta() > 0:
                self.onZoomIn()
            else:
                self.onZoomOut()
        else:
            HTMLTabWidget.wheelEvent( self, event )
        return

    def setHTML( self, content ):
        " Sets the content from the given string "
        HTMLTabWidget.setHTML( self, content )
        self.zoomTo( Settings().zoom )
        return

    def loadFormFile( self, path ):
        " Loads the content from the given file "
        HTMLTabWidget.loadFormFile( self, path )
        self.zoomTo( Settings().zoom )
        return

    def getType( self ):
        " Tells the widget type "
        return MainWindowTabWidgetBase.DiffViewer

    def getLanguage( self ):
        " Tells the content language "
        return "diff"

    def onZoomReset( self ):
        " Triggered when the zoom reset button is pressed "
        if Settings().zoom != 0:
            self.textEditorZoom.emit( 0 )
        return True

    def onZoomIn( self ):
        " Triggered when the zoom in button is pressed "
        if Settings().zoom < 20:
            self.textEditorZoom.emit( Settings().zoom + 1 )
        return True

    def onZoomOut( self ):
        " Triggered when the zoom out button is pressed "
        if Settings().zoom > -10:
            self.textEditorZoom.emit( Settings().zoom - 1 )
        return True
