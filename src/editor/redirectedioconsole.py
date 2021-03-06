#
# -*- coding: utf-8 -*-
#
# codimension - graphics python two-way code editor and analyzer
# Copyright (C) 2010  Sergey Satskiy sergey.satskiy@gmail.com
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

" Redirected IO console implementation "


from texteditor import TextEditor
from PyQt4.QtCore import Qt, SIGNAL, QSize, QPoint, QEvent, pyqtSignal
from PyQt4.QtGui import ( QToolBar, QFont, QFontMetrics, QHBoxLayout, QWidget,
                          QAction, QSizePolicy, QToolTip, QMenu, QToolButton,
                          QActionGroup, QApplication )
from PyQt4.Qsci import QsciScintilla
from ui.mainwindowtabwidgetbase import MainWindowTabWidgetBase
from utils.fileutils import TexFileType
from utils.pixmapcache import PixmapCache
from utils.globals import GlobalData
from utils.settings import Settings
from redirectedmsg import IOConsoleMessages, IOConsoleMsg
from scintillawrap import ScintillaWrapper



class RedirectedIOConsole( TextEditor ):
    " Widget which implements the redirected IO console "

    TIMESTAMP_MARGIN = 0     # Introduced here

    stdoutStyle = 1
    stderrStyle = 2
    stdinStyle = 3
    marginStyle = 4

    MODE_OUTPUT = 0
    MODE_INPUT = 1

    def __init__( self, parent ):
        TextEditor.__init__( self, parent, None )
        self.zoomTo( Settings().zoom )

        # line number -> [ timestamps ]
        self.__marginTooltip = {}
        self.mode = self.MODE_OUTPUT
        self.lastOutputPos = None
        self.inputEcho = True
        self.inputBuffer = ""
        self.__messages = IOConsoleMessages()

        self.__initGeneralSettings()
        self.__initMargins()

        self.__timestampTooltipShown = False
        self.__initMessageMarkers()
        self._updateDwellingTime()

        self.installEventFilter( self )
        return

    def zoomTo( self, zoomValue ):
        " Reimplemented zoomTo "
        QsciScintilla.zoomTo( self, zoomValue )
        self.zoom = zoomValue
        return

    def eventFilter( self, obj, event ):
        " Event filter to catch shortcuts on UBUNTU "
        if event.type() == QEvent.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            if modifiers == Qt.ShiftModifier | Qt.ControlModifier:
                if key == Qt.Key_Up:
                    self.selectParagraphUp()
                    return True
                if key == Qt.Key_Down:
                    self.selectParagraphDown()
                    return True
                if key == Qt.Key_C:
                    self.onCtrlShiftC()
                    return True
            if modifiers == Qt.ShiftModifier:
                if key == Qt.Key_End:
                    self.selectTillDisplayEnd()
                    return True
                if key == Qt.Key_Home:
                    return self._onShiftHome()
                if key == Qt.Key_Insert:
                    return self.insertText()
                if key == Qt.Key_Delete:
                    return self.onShiftDel()
            if modifiers == Qt.ControlModifier:
                if key == Qt.Key_V:
                    return self.insertText()
                if key == Qt.Key_X:
                    return self.onShiftDel()
                if key in [ Qt.Key_C, Qt.Key_Insert ]:
                    return self.onCtrlC()
                if key == Qt.Key_Apostrophe:       # Ctrl + '
                    return self._onHighlight()
                if key == Qt.Key_Period:
                    return self._onNextHighlight() # Ctrl + .
                if key == Qt.Key_Comma:
                    return self._onPrevHighlight() # Ctrl + ,
                if key == Qt.Key_Minus:
                    return self._parent.onZoomOut()
                if key == Qt.Key_Equal:
                    return self._parent.onZoomIn()
                if key == Qt.Key_0:
                    return self._parent.onZoomReset()
                if key == Qt.Key_Home:
                    return self.onFirstChar()
                if key == Qt.Key_End:
                    return self.onLastChar()
            if modifiers == Qt.AltModifier:
                if key == Qt.Key_Left:
                    self.wordPartLeft()
                    return True
                if key == Qt.Key_Right:
                    self.wordPartRight()
                    return True
                if key == Qt.Key_Up:
                    self.paragraphUp()
                    return True
                if key == Qt.Key_Down:
                    self.paragraphDown()
                    return True
            if modifiers == Qt.KeypadModifier | Qt.ControlModifier:
                if key == Qt.Key_Minus:
                    return self._parent.onZoomOut()
                if key == Qt.Key_Plus:
                    return self._parent.onZoomIn()
                if key == Qt.Key_0:
                    return self._parent.onZoomReset()
            if modifiers == Qt.NoModifier:
                if key == Qt.Key_Home:
                    return self._onHome()
                if key == Qt.Key_End:
                    self.moveToLineEnd()
                    return True
                if key in [ Qt.Key_Delete, Qt.Key_Backspace ]:
                    if not self.__isCutDelAvailable():
                        return True

        return False

    def keyPressEvent( self, event ):
        " Triggered when a key is pressed "
        key = event.key()
        if key == Qt.Key_Escape:
            self.clearSearchIndicators()
            return

        if self.mode == self.MODE_OUTPUT:
            ScintillaWrapper.keyPressEvent( self, event )
            return

        # It is an input mode
        txt = event.text()
        if len( txt ) and txt >= ' ':
            # Printable character
            if self.currentPosition() < self.lastOutputPos:
                # Out of the input zone
                return

            if self.inputEcho:
                startPos = self.currentPosition()
                self.SendScintilla( self.SCI_STARTSTYLING, startPos, 31 )
                ScintillaWrapper.keyPressEvent( self, event )
                endPos = self.currentPosition()
                self.SendScintilla( self.SCI_SETSTYLING,
                                    endPos - startPos, self.stdinStyle )
            else:
                self.inputBuffer += txt
            return

        # Non-printable character or some other key
        if key == Qt.Key_Enter or key == Qt.Key_Return:
            userInput = str( self.__getUserInput() )
            self.switchMode( self.MODE_OUTPUT )
            timestampLine, _ = self.getEndPosition()
            self.append( '\n' )
            self.clearUndoHistory()
            line, pos = self.getEndPosition()
            self.setCursorPosition( line, pos )
            self.ensureLineVisible( line )
            endPos = self.currentPosition()
            startPos = self.positionBefore( endPos )
            self.SendScintilla( self.SCI_STARTSTYLING, startPos, 31 )
            self.SendScintilla( self.SCI_SETSTYLING,
                                endPos - startPos, self.stdinStyle )
            msg = IOConsoleMsg( IOConsoleMsg.STDIN_MESSAGE,
                                userInput + "\n" )
            self.__messages.append( msg )
            self.__addTooltip( timestampLine, msg.getTimestamp() )
            self.emit( SIGNAL( 'UserInput' ), userInput )
            return
        if key == Qt.Key_Backspace:
            if self.currentPosition() == self.lastOutputPos:
                if self.inputEcho == False:
                    self.inputBuffer = self.inputBuffer[ : -1 ]
                return

        ScintillaWrapper.keyPressEvent( self, event )
        return

    def insertText( self ):
        " Triggered when insert is requested "
        if self.isReadOnly():
            return True

        # Check what is in the buffer
        text = QApplication.clipboard().text()
        if '\n' in text or '\r' in text:
            return True

        if not self.inputEcho:
            self.inputBuffer += text
            return True

        startPos = self.currentPosition()
        TextEditor.paste( self )
        endPos = self.currentPosition()

        self.SendScintilla( self.SCI_STARTSTYLING, startPos, 31 )
        self.SendScintilla( self.SCI_SETSTYLING,
                            endPos - startPos, self.stdinStyle )
        return True

    def __getUserInput( self ):
        " Provides the collected user input "
        if self.mode != self.MODE_INPUT:
            return ""
        if self.inputEcho:
            line, pos = self.getEndPosition()
            _, startPos = self.lineIndexFromPosition( self.lastOutputPos )
            return self.getTextAtPos( line, startPos, pos - startPos )
        value = self.inputBuffer
        self.inputBuffer = ""
        return value

    def __initGeneralSettings( self ):
        " Sets some generic look and feel "
        skin = GlobalData().skin

        self.setEolVisibility( Settings().ioconsoleshoweol )
        if Settings().ioconsolelinewrap:
            self.setWrapMode( QsciScintilla.WrapWord )
        else:
            self.setWrapMode( QsciScintilla.WrapNone )
        if Settings().ioconsoleshowspaces:
            self.setWhitespaceVisibility( QsciScintilla.WsVisible )
        else:
            self.setWhitespaceVisibility( QsciScintilla.WsInvisible )

        self.setPaper( skin.ioconsolePaper )
        self.setColor( skin.ioconsoleColor )

        self.setModified( False )
        self.setReadOnly( True )

        # If a lexer id bind then unnecessery visual effects appear like
        # disappearing assingned text style. As the lexer actually not required
        # at all I prefer not to struggle with styling but just not to use any
        # lexers
        # self.bindLexer( "", TexFileType )

        self.setCurrentLineHighlight( False, None )
        self.setEdgeMode( QsciScintilla.EdgeNone )
        self.setCursorStyle()
        self.setAutoIndent( False )
        return

    def _onCursorPositionChanged( self, line, pos ):
        " Called when the cursor changed position "
        self.setCursorStyle()
        return

    def setCursorStyle( self ):
        " Sets the cursor style depending on the mode and the cursor pos "
        self.SendScintilla( self.SCI_SETCARETPERIOD, 750 )
        if self.mode == self.MODE_OUTPUT:
            self.SendScintilla( self.SCI_SETCARETSTYLE, self.CARETSTYLE_LINE )
        else:
            currentPos = self.currentPosition()
            if currentPos >= self.lastOutputPos:
                self.SendScintilla( self.SCI_SETCARETSTYLE,
                                    self.CARETSTYLE_BLOCK )
                self.setReadOnly( False )
            else:
                self.SendScintilla( self.SCI_SETCARETSTYLE,
                                    self.CARETSTYLE_LINE )
                self.setReadOnly( True )
        return

    def switchMode( self, newMode ):
        " Switches between input/output mode "
        self.mode = newMode
        if self.mode == self.MODE_OUTPUT:
            self.lastOutputPos = None
            self.setReadOnly( True )
            self.inputEcho = True
            self.inputBuffer = ""
        else:
            line, pos = self.getEndPosition()
            self.lastOutputPos = self.positionFromLineIndex( line, pos )
            self.setReadOnly( False )
            self.setCursorPosition( line, pos )
            self.ensureLineVisible( line )
        self.setCursorStyle()
        return

    def __initMargins( self ):
        " Initializes the IO console margins "

        # The supported margins: timestamp

        # reset standard margins settings
        for margin in xrange( 5 ):
            self.setMarginLineNumbers( margin, False )
            self.setMarginMarkerMask( margin, 0 )
            self.setMarginWidth( margin, 0 )
            self.setMarginSensitivity( margin, False )

        self.setMarginType( self.TIMESTAMP_MARGIN, self.TextMargin )
        self.setMarginMarkerMask( self.TIMESTAMP_MARGIN, 0 )

        skin = GlobalData().skin
        self.setMarginsBackgroundColor( skin.ioconsolemarginPaper )
        self.setMarginsForegroundColor( skin.ioconsolemarginColor )

        # Define margin style
        self.SendScintilla( self.SCI_STYLESETFORE, self.marginStyle,
                            self.convertColor( skin.ioconsolemarginColor ) )
        self.SendScintilla( self.SCI_STYLESETBACK, self.marginStyle,
                            self.convertColor( skin.ioconsolemarginPaper ) )
        self.SendScintilla( self.SCI_STYLESETFONT, self.marginStyle,
                            str( skin.ioconsolemarginFont.family() ) )
        self.SendScintilla( self.SCI_STYLESETSIZE, self.marginStyle,
                            skin.ioconsolemarginFont.pointSize() )
        self.SendScintilla( self.SCI_STYLESETBOLD, self.marginStyle,
                            skin.ioconsolemarginFont.bold() )
        self.SendScintilla( self.SCI_STYLESETITALIC, self.marginStyle,
                            skin.ioconsolemarginFont.italic() )

        self.setMarginsFont( skin.ioconsolemarginFont )
        self.setTimestampMarginWidth()
        return

    def __initMessageMarkers( self ):
        " Initializes the marker used for the IDE messages "
        skin = GlobalData().skin
        self.ideMessageMarker = self.markerDefine( QsciScintilla.Background )
        self.setMarkerForegroundColor( skin.ioconsoleIDEMsgColor,
                                       self.ideMessageMarker )
        self.setMarkerBackgroundColor( skin.ioconsoleIDEMsgPaper,
                                       self.ideMessageMarker )

        # stdout style
        self.SendScintilla( self.SCI_STYLESETFORE, self.stdoutStyle,
                            self.convertColor( skin.ioconsoleStdoutColor ) )
        self.SendScintilla( self.SCI_STYLESETBACK, self.stdoutStyle,
                            self.convertColor( skin.ioconsoleStdoutPaper ) )
        self.SendScintilla( self.SCI_STYLESETBOLD, self.stdoutStyle,
                            skin.ioconsoleStdoutBold != 0 )
        self.SendScintilla( self.SCI_STYLESETITALIC, self.stdoutStyle,
                            skin.ioconsoleStdoutItalic != 0 )

        # stdout style
        self.SendScintilla( self.SCI_STYLESETFORE, self.stderrStyle,
                            self.convertColor( skin.ioconsoleStderrColor ) )
        self.SendScintilla( self.SCI_STYLESETBACK, self.stderrStyle,
                            self.convertColor( skin.ioconsoleStderrPaper ) )
        self.SendScintilla( self.SCI_STYLESETBOLD, self.stderrStyle,
                            skin.ioconsoleStderrBold != 0 )
        self.SendScintilla( self.SCI_STYLESETITALIC, self.stderrStyle,
                            skin.ioconsoleStderrItalic != 0 )

        # stdin style
        self.SendScintilla( self.SCI_STYLESETFORE, self.stdinStyle,
                            self.convertColor( skin.ioconsoleStdinColor ) )
        self.SendScintilla( self.SCI_STYLESETBACK, self.stdinStyle,
                            self.convertColor( skin.ioconsoleStdinPaper ) )
        self.SendScintilla( self.SCI_STYLESETBOLD, self.stdinStyle,
                            skin.ioconsoleStdinBold != 0 )
        self.SendScintilla( self.SCI_STYLESETITALIC, self.stdinStyle,
                            skin.ioconsoleStdinItalic != 0 )
        return

    def _marginClicked( self, margin, line, modifiers ):
        return

    def _styleNeeded( self, position ):
        return

    def _updateDwellingTime( self ):
        " There is always something to show "
        self.SendScintilla( self.SCI_SETMOUSEDWELLTIME, 250 )
        return

    def _onDwellStart( self, position, x, y ):
        " Triggered when mouse started to dwell "
        if not self.underMouse():
            return

        marginNumber = self._marginNumber( x )
        if marginNumber == self.TIMESTAMP_MARGIN:
            self.__showTimestampTooltip( position, x, y )
            return

        TextEditor._onDwellStart( self, position, x, y )
        return

    def __showTimestampTooltip( self, position, x, y ):
        " Shows a tooltip on the timestamp margin "
        # Calculate the line
        pos = self.SendScintilla( self.SCI_POSITIONFROMPOINT, x, y )
        line, _ = self.lineIndexFromPosition( pos )

        tooltip = self.__getTimestampMarginTooltip( line )
        if not tooltip:
            return

        QToolTip.showText( self.mapToGlobal( QPoint( x, y ) ), tooltip )
        self.__timestampTooltipShown = True
        return

    def __getTimestampMarginTooltip( self, line ):
        " Provides the margin tooltip "
        if line in self.__marginTooltip:
            return "\n".join( self.__marginTooltip[ line ] )
        return None

    def _onDwellEnd( self, position, x, y ):
        " Triggered when mouse ended to dwell "
        if self.__timestampTooltipShown:
            self.__timestampTooltipShown = False
            QToolTip.hideText()
        return

    def _initContextMenu( self ):
        " Called to initialize a context menu "
        self._menu = QMenu( self )
        self.__menuUndo = self._menu.addAction(
                                    PixmapCache().getIcon( 'undo.png' ),
                                    '&Undo', self.onUndo, "Ctrl+Z" )
        self.__menuRedo = self._menu.addAction(
                                    PixmapCache().getIcon( 'redo.png' ),
                                    '&Redo', self.onRedo, "Ctrl+Y" )
        self._menu.addSeparator()
        self.__menuCut = self._menu.addAction(
                                    PixmapCache().getIcon( 'cutmenu.png' ),
                                    'Cu&t', self.onShiftDel, "Ctrl+X" )
        self.__menuCopy = self._menu.addAction(
                                    PixmapCache().getIcon( 'copymenu.png' ),
                                    '&Copy', self.onCtrlC, "Ctrl+C" )
        self.__menucopyTimestamp = self._menu.addAction(
                                    PixmapCache().getIcon( 'copymenu.png' ),
                                    '&Copy all with timestamps',
                                    self.onCtrlShiftC, "Ctrl+Shift+C" )
        self.__menuPaste = self._menu.addAction(
                                    PixmapCache().getIcon( 'pastemenu.png' ),
                                    '&Paste', self.insertText, "Ctrl+V" )
        self.__menuSelectAll = self._menu.addAction(
                                PixmapCache().getIcon( 'selectallmenu.png' ),
                                'Select &all', self.selectAll, "Ctrl+A" )
        self._menu.addSeparator()
        self.__menuOpenAsFile = self._menu.addAction(
                                PixmapCache().getIcon( 'filemenu.png' ),
                                'O&pen as file', self.openAsFile )
        self.__menuDownloadAndShow = self._menu.addAction(
                                PixmapCache().getIcon( 'filemenu.png' ),
                                'Do&wnload and show', self.downloadAndShow )
        self.__menuOpenInBrowser = self._menu.addAction(
                                PixmapCache().getIcon( 'homepagemenu.png' ),
                                'Open in browser', self.openInBrowser )
        self._menu.addSeparator()

        self._menu.aboutToShow.connect( self._contextMenuAboutToShow )
        self._menu.aboutToHide.connect( self._contextMenuAboutToHide )

        return

    def setTimestampMarginWidth( self ):
        " Sets the timestamp margin width "
        settings = Settings()
        if settings.ioconsoleshowmargin:
            skin = GlobalData().skin
            font = QFont( skin.ioconsolemarginFont )
            font.setPointSize( font.pointSize() + settings.zoom )
            # The second parameter of the QFontMetrics is essential!
            # If it is not there then the width is not calculated properly.
            fontMetrics = QFontMetrics( font, self )
            # W is for extra space at the right of the timestamp
            width = fontMetrics.width( '88:88:88.888W' )
            self.setMarginWidth( self.TIMESTAMP_MARGIN, width )
        else:
            self.setMarginWidth( self.TIMESTAMP_MARGIN, 0 )
        return

    def contextMenuEvent( self, event ):
        " Called just before showing a context menu "
        event.accept()
        if self._marginNumber( event.x() ) is None:
            # Editing area context menu
            self._menu.popup( event.globalPos() )
        else:
            # Menu for a margin
            pass
        return

    def _contextMenuAboutToShow( self ):
        " IO Console context menu is about to show "
        self.__menuUndo.setEnabled( self.isUndoAvailable() )
        self.__menuRedo.setEnabled( self.isRedoAvailable() )

        pasteText = QApplication.clipboard().text()
        pasteEnable = pasteText != "" and \
                      '\n' not in pasteText and \
                      '\r' not in pasteText and \
                      not self.isReadOnly()

        # Need to make decision about menu items for modifying the input
        self.__menuCut.setEnabled( self.__isCutDelAvailable() )
        self.__menuCopy.setEnabled( self.__messages.size > 0 )
        self.__menucopyTimestamp.setEnabled( self.__messages.size > 0 )
        self.__menuPaste.setEnabled( pasteEnable )
        self.__menuSelectAll.setEnabled( self.__messages.size > 0 )

        self.__menuOpenAsFile.setEnabled( self.openAsFileAvailable() )
        self.__menuDownloadAndShow.setEnabled(
                                        self.downloadAndShowAvailable() )
        self.__menuOpenInBrowser.setEnabled(
                                        self.downloadAndShowAvailable() )
        return

    def _contextMenuAboutToHide( self ):
        " IO console context menu is about to hide "
        self.__menuUndo.setEnabled( True )
        self.__menuRedo.setEnabled( True )
        self.__menuCut.setEnabled( True )
        self.__menuCopy.setEnabled( True )
        self.__menucopyTimestamp.setEnabled( True )
        self.__menuPaste.setEnabled( True )
        self.__menuSelectAll.setEnabled( True )
        self.__menuOpenAsFile.setEnabled( True )
        self.__menuDownloadAndShow.setEnabled( True )
        self.__menuOpenInBrowser.setEnabled( True )
        return

    def __isCutDelAvailable( self ):
        " Returns True if cutting or deletion is possible "
        if self.isReadOnly():
            return False

        minPos = self.getSelectionStart()
        if minPos < self.lastOutputPos:
            return False

        return True

    def onShiftDel( self ):
        " Deletes the selected text "
        if self.hasSelectedText():
            if self.__isCutDelAvailable():
                self.cut()
            return True
        return True

    def onUndo( self ):
        if self.isUndoAvailable():
            self.undo()
        return

    def onRedo( self ):
        if self.isRedoAvailable():
            self.redo()
        return

    def onCtrlShiftC( self ):
        " Copy all with timestamps "
        QApplication.clipboard().setText(
                            self.__messages.renderWithTimestamps() )
        return True

    def appendIDEMessage( self, text ):
        " Appends an IDE message "
        msg = IOConsoleMsg( IOConsoleMsg.IDE_MESSAGE, text )
        self.__appendMessage( msg )
        return

    def appendStdoutMessage( self, text ):
        " Appends an stdout message "
        msg = IOConsoleMsg( IOConsoleMsg.STDOUT_MESSAGE, text )
        self.__appendMessage( msg )
        return

    def appendStderrMessage( self, text ):
        " Appends an stderr message "
        msg = IOConsoleMsg( IOConsoleMsg.STDERR_MESSAGE, text )
        self.__appendMessage( msg )
        return

    def __appendMessage( self, message ):
        " Appends a new message to the console "
        if not self.__messages.append( message ):
            # There was no trimming of the message list
            self.__renderMessage( message )
        else:
            # Some messages were stripped
            self.renderContent()
        return

    def renderContent( self ):
        " Regenerates the viewer content "
        self.clear()
        self.__marginTooltip = {}
        for msg in self.__messages.msgs:
            self.__renderMessage( msg )
        return

    def __renderMessage( self, msg ):
        " Adds a single message "
        timestamp = msg.getTimestamp()
        if msg.msgType == IOConsoleMsg.IDE_MESSAGE:
            # Check the text. Append \n if needed. Append the message
            line, pos = self.getEndPosition()
            if pos != 0:
                self.append( "\n" )
                startMarkLine = line + 1
            else:
                startMarkLine = line
            self.append( msg.msgText )
            if not msg.msgText.endswith( "\n" ):
                self.append( "\n" )
            line, pos = self.getEndPosition()
            for lineNo in xrange( startMarkLine, line ):
                self.markerAdd( lineNo, self.ideMessageMarker )
                self.__addTooltip( lineNo, timestamp )
        else:
            if self._parent.hiddenMessage( msg ):
                return
            line, pos = self.getEndPosition()
            startPos = self.positionFromLineIndex( line, pos )
            if pos != 0:
                self.__addTooltip( line, timestamp )
                startTimestampLine = line + 1
            else:
                startTimestampLine = line
            self.append( msg.msgText )
            line, pos = self.getEndPosition()
            if pos != 0:
                endTimestampLine = line
            else:
                endTimestampLine = line - 1
            for lineNo in xrange( startTimestampLine, endTimestampLine + 1 ):
                self.__addTooltip( lineNo, timestamp )

            if msg.msgType == IOConsoleMsg.STDERR_MESSAGE:
                # Highlight as stderr
                styleNo = self.stderrStyle
            elif msg.msgType == IOConsoleMsg.STDOUT_MESSAGE:
                # Highlight as stdout
                styleNo = self.stdoutStyle
            else:
                styleNo = self.stdinStyle

            line, pos = self.getEndPosition()
            endPos = self.positionFromLineIndex( line, pos )

            self.SendScintilla( self.SCI_STARTSTYLING, startPos, 31 )
            line, pos = self.getEndPosition()
            endPos = self.positionFromLineIndex( line, pos )
            self.SendScintilla( self.SCI_SETSTYLING,
                                endPos - startPos, styleNo )

        self.clearUndoHistory()
        if Settings().ioconsoleautoscroll:
            line, pos = self.getEndPosition()
            self.gotoLine( line + 1, pos + 1 )
        return

    def __addTooltip( self, lineNo, timestamp ):
        " Adds a tooltip into the dictionary "
        if lineNo in self.__marginTooltip:
            self.__marginTooltip[ lineNo ].append( timestamp )
        else:
            self.__marginTooltip[ lineNo ] = [ timestamp ]
            self.setMarginText( lineNo, timestamp, self.marginStyle )
        return

    def clearData( self ):
        " Clears the collected data "
        self.__messages.clear()
        self.__marginTooltip = {}
        return

    def clearAll( self ):
        " Clears both data and visible content "
        self.clearData()
        self.clear()
        self.clearUndoHistory()
        return




class IOConsoleTabWidget( QWidget, MainWindowTabWidgetBase ):
    " IO console tab widget "

    textEditorZoom = pyqtSignal( int )
    settingUpdated = pyqtSignal()

    def __init__( self, parent ):

        MainWindowTabWidgetBase.__init__( self )
        QWidget.__init__( self, parent )

        self.__viewer = RedirectedIOConsole( self )
        self.connect( self.__viewer, SIGNAL( 'UserInput' ), self.__onUserInput )

        self.__createLayout()
        return

    def __onUserInput( self, userInput ):
        " Triggered when the user finished input in the redirected IO console "
        self.emit( SIGNAL( 'UserInput' ), userInput )
        self.__clearButton.setEnabled( True )
        return

    def __createLayout( self ):
        " Creates the toolbar and layout "

        # Buttons
        self.__printButton = QAction( PixmapCache().getIcon( 'printer.png' ),
                                      'Print', self )
        self.__printButton.triggered.connect( self.__onPrint )
        self.__printButton.setEnabled( False )
        self.__printButton.setVisible( False )

        self.__printPreviewButton = QAction(
                                PixmapCache().getIcon( 'printpreview.png' ),
                                'Print preview', self )
        self.__printPreviewButton.triggered.connect( self.__onPrintPreview )
        self.__printPreviewButton.setEnabled( False )
        self.__printPreviewButton.setVisible( False )

        # self.__sendUpButton = QAction( PixmapCache().getIcon('sendioup.png'),
        #                                'Send to Main Editing Area', self )
        # self.__sendUpButton.triggered.connect( self.__sendUp )

        self.__filterMenu = QMenu( self )
        self.__filterMenu.aboutToShow.connect( self.__filterAboutToShow )
        self.__filterGroup = QActionGroup( self )
        self.__filterShowAllAct = self.__filterMenu.addAction( "Show all" )
        self.__filterShowAllAct.setCheckable( True )
        self.__filterShowAllAct.setActionGroup( self.__filterGroup )
        self.__filterShowAllAct.triggered.connect( self.__onFilterShowAll )
        self.__filterShowStdoutAct = self.__filterMenu.addAction(
                                                "Show stdin and stdout" )
        self.__filterShowStdoutAct.setCheckable( True )
        self.__filterShowStdoutAct.setActionGroup( self.__filterGroup )
        self.__filterShowStdoutAct.triggered.connect( self.__onFilterShowStdout )
        self.__filterShowStderrAct = self.__filterMenu.addAction(
                                                "Show stdin and stderr" )
        self.__filterShowStderrAct.setCheckable( True )
        self.__filterShowStderrAct.setActionGroup( self.__filterGroup )
        self.__filterShowStderrAct.triggered.connect( self.__onFilterShowStderr )
        self.__filterButton = QToolButton( self )
        self.__filterButton.setIcon( PixmapCache().getIcon( 'iofilter.png' ) )
        self.__filterButton.setToolTip( 'Filtering settings' )
        self.__filterButton.setPopupMode( QToolButton.InstantPopup )
        self.__filterButton.setMenu( self.__filterMenu )
        self.__filterButton.setFocusPolicy( Qt.NoFocus )

        self.__settingsMenu = QMenu( self )
        self.__settingsMenu.aboutToShow.connect( self.__settingsAboutToShow )
        self.__wrapLongLinesAct = self.__settingsMenu.addAction(
                                                "Wrap long lines" )
        self.__wrapLongLinesAct.setCheckable( True )
        self.__wrapLongLinesAct.triggered.connect( self.__onWrapLongLines )
        self.__showEOLAct = self.__settingsMenu.addAction( "Show EOL" )
        self.__showEOLAct.setCheckable( True )
        self.__showEOLAct.triggered.connect( self.__onShowEOL )
        self.__showWhitespacesAct = self.__settingsMenu.addAction(
                                                "Show whitespaces" )
        self.__showWhitespacesAct.setCheckable( True )
        self.__showWhitespacesAct.triggered.connect( self.__onShowWhitespaces )
        self.__autoscrollAct = self.__settingsMenu.addAction( "Autoscroll" )
        self.__autoscrollAct.setCheckable( True )
        self.__autoscrollAct.triggered.connect( self.__onAutoscroll )
        self.__showMarginAct = self.__settingsMenu.addAction(
                                                "Show timestamp margin" )
        self.__showMarginAct.setCheckable( True )
        self.__showMarginAct.triggered.connect( self.__onShowMargin )

        self.__settingsButton = QToolButton( self )
        self.__settingsButton.setIcon(
                            PixmapCache().getIcon( 'iosettings.png' ) )
        self.__settingsButton.setToolTip( 'View settings' )
        self.__settingsButton.setPopupMode( QToolButton.InstantPopup )
        self.__settingsButton.setMenu( self.__settingsMenu )
        self.__settingsButton.setFocusPolicy( Qt.NoFocus )

        spacer = QWidget()
        spacer.setSizePolicy( QSizePolicy.Expanding, QSizePolicy.Expanding )
        self.__clearButton = QAction( PixmapCache().getIcon( 'trash.png' ),
                                      'Clear', self )
        self.__clearButton.triggered.connect( self.clear )

        # The toolbar
        toolbar = QToolBar( self )
        toolbar.setOrientation( Qt.Vertical )
        toolbar.setMovable( False )
        toolbar.setAllowedAreas( Qt.RightToolBarArea )
        toolbar.setIconSize( QSize( 16, 16 ) )
        toolbar.setFixedWidth( 28 )
        toolbar.setContentsMargins( 0, 0, 0, 0 )

        # toolbar.addAction( self.__sendUpButton )
        toolbar.addAction( self.__printPreviewButton )
        toolbar.addAction( self.__printButton )
        toolbar.addWidget( self.__filterButton )
        toolbar.addWidget( self.__settingsButton )
        toolbar.addWidget( spacer )
        toolbar.addAction( self.__clearButton )

        hLayout = QHBoxLayout()
        hLayout.setContentsMargins( 0, 0, 0, 0 )
        hLayout.setSpacing( 0 )
        hLayout.addWidget( toolbar )
        hLayout.addWidget( self.__viewer )

        self.setLayout( hLayout )
        return

    def onZoomReset( self ):
        " Triggered when the zoom reset button is pressed "
        if self.__viewer.zoom != 0:
            self.textEditorZoom.emit( 0 )
        return True

    def onZoomIn( self ):
        " Triggered when the zoom in button is pressed "
        if self.__viewer.zoom < 20:
            self.textEditorZoom.emit( self.__viewer.zoom + 1 )
        return True

    def onZoomOut( self ):
        " Triggered when the zoom out button is pressed "
        if self.__viewer.zoom > -10:
            self.textEditorZoom.emit( self.__viewer.zoom - 1 )
        return True

    def __onPrint( self ):
        " Triggered when the print button is pressed "
        pass

    def __onPrintPreview( self ):
        " triggered when the print preview button is pressed "
        pass

    def setFocus( self ):
        " Overridden setFocus "
        self.__viewer.setFocus()
        return

    def onOpenImport( self ):
        " Triggered when Ctrl+I is received "
        return True

    def __sendUp( self ):
        " Triggered when requested to move the console up "
        return

    def __filterAboutToShow( self ):
        " Triggered when filter menu is about to show "
        showAll = Settings().ioconsoleshowstdin and \
                  Settings().ioconsoleshowstdout and \
                  Settings().ioconsoleshowstderr
        onlyStdout = Settings().ioconsoleshowstdin and \
                     Settings().ioconsoleshowstdout and \
                     not Settings().ioconsoleshowstderr
        onlyStderr = Settings().ioconsoleshowstdin and \
                     not Settings().ioconsoleshowstdout and \
                     Settings().ioconsoleshowstderr
        self.__filterShowAllAct.setChecked( showAll )
        self.__filterShowStdoutAct.setChecked( onlyStdout )
        self.__filterShowStderrAct.setChecked( onlyStderr )
        return

    def __onFilterShowAll( self ):
        " Triggered when filter show all is clicked "
        if Settings().ioconsoleshowstdin == True and \
           Settings().ioconsoleshowstdout == True and \
           Settings().ioconsoleshowstderr == True:
            return

        Settings().ioconsoleshowstdin = True
        Settings().ioconsoleshowstdout = True
        Settings().ioconsoleshowstderr = True
        self.__viewer.renderContent()
        return

    def __onFilterShowStdout( self ):
        " Triggered when filter show stdout only is clicked "
        if Settings().ioconsoleshowstdin == True and \
           Settings().ioconsoleshowstdout == True and \
           Settings().ioconsoleshowstderr == False:
            return

        Settings().ioconsoleshowstdin = True
        Settings().ioconsoleshowstdout = True
        Settings().ioconsoleshowstderr = False
        self.__viewer.renderContent()
        return

    def __onFilterShowStderr( self ):
        " Triggered when filter show stderr only is clicked "
        if Settings().ioconsoleshowstdin == True and \
           Settings().ioconsoleshowstdout == False and \
           Settings().ioconsoleshowstderr == True:
            return

        Settings().ioconsoleshowstdin = True
        Settings().ioconsoleshowstdout = False
        Settings().ioconsoleshowstderr = True
        self.__viewer.renderContent()
        return

    def __settingsAboutToShow( self ):
        " Settings menu is about to show "
        self.__wrapLongLinesAct.setChecked( Settings().ioconsolelinewrap )
        self.__showEOLAct.setChecked( Settings().ioconsoleshoweol )
        self.__showWhitespacesAct.setChecked( Settings().ioconsoleshowspaces )
        self.__autoscrollAct.setChecked( Settings().ioconsoleautoscroll )
        self.__showMarginAct.setChecked( Settings().ioconsoleshowmargin )
        return

    def __onWrapLongLines( self ):
        " Triggered when long lines setting is changed "
        Settings().ioconsolelinewrap = not Settings().ioconsolelinewrap
        self.settingUpdated.emit()
        return

    def __onShowEOL( self ):
        " Triggered when show EOL is changed "
        Settings().ioconsoleshoweol = not Settings().ioconsoleshoweol
        self.settingUpdated.emit()
        return

    def __onShowWhitespaces( self ):
        " Triggered when show whitespaces is changed "
        Settings().ioconsoleshowspaces = not Settings().ioconsoleshowspaces
        self.settingUpdated.emit()
        return

    def __onAutoscroll( self ):
        " Triggered when autoscroll is changed "
        Settings().ioconsoleautoscroll = not Settings().ioconsoleautoscroll
        return

    def __onShowMargin( self ):
        " Triggered when show margin is changed "
        Settings().ioconsoleshowmargin = not Settings().ioconsoleshowmargin
        self.settingUpdated.emit()
        return

    def clear( self ):
        " Triggered when requested to clear the console "
        self.__viewer.clearAll()
        return

    def consoleSettingsUpdated( self ):
        " Triggered when one of the consoles updated a common setting "
        if Settings().ioconsolelinewrap:
            self.__viewer.setWrapMode( QsciScintilla.WrapWord )
        else:
            self.__viewer.setWrapMode( QsciScintilla.WrapNone )
        self.__viewer.setEolVisibility( Settings().ioconsoleshoweol )
        if Settings().ioconsoleshowspaces:
            self.__viewer.setWhitespaceVisibility( QsciScintilla.WsVisible )
        else:
            self.__viewer.setWhitespaceVisibility( QsciScintilla.WsInvisible )
        self.__viewer.setTimestampMarginWidth()
        return

    def resizeEvent( self, event ):
        QWidget.resizeEvent( self, event )
        return
    def onPylint( self ):
        return True
    def onPymetrics( self ):
        return True
    def onRunScript( self, action = False ):
        return True
    def onRunScriptSettings( self ):
        return True
    def onProfileScript( self, action = False ):
        return True
    def onProfileScriptSettings( self ):
        return True
    def onImportDgm( self, action = None ):
        return True
    def onImportDgmTuned( self ):
        return True
    def shouldAcceptFocus( self ):
        return True
    def onNavigationBar( self ):
        pass

    def writeFile( self, fileName ):
        " Writes the text to a file "
        return self.__viewer.writeFile( fileName )

    def updateModificationTime( self, fileName ):
        return

    def appendIDEMessage( self, text ):
        " Appends an IDE message "
        self.__viewer.appendIDEMessage( text )
        return

    def appendStdoutMessage( self, text ):
        " Appends an stdout message "
        self.__viewer.appendStdoutMessage( text )
        return

    def appendStderrMessage( self, text ):
        " Appends an stderr message "
        self.__viewer.appendStderrMessage( text )
        return

    def hiddenMessage( self, msg ):
        " Returns True if the message should not be shown "
        if msg.msgType == IOConsoleMsg.STDERR_MESSAGE and \
           not Settings().ioconsoleshowstderr:
            return True
        if msg.msgType == IOConsoleMsg.STDOUT_MESSAGE and \
           not Settings().ioconsoleshowstdout:
            return True
        return False

    def zoomTo( self, zoomValue ):
        " Sets the new zoom value "
        self.__viewer.zoomTo( zoomValue )
        self.__viewer.setTimestampMarginWidth()
        return

    def rawInput( self, prompt, echo ):
        " Triggered when raw input is requested "
        echo = int( echo )
        if echo == 0:
            self.__viewer.inputEcho = False
        else:
            self.__viewer.inputEcho = True

        if prompt:
            self.appendStdoutMessage( prompt )
        self.__clearButton.setEnabled( False )
        self.__viewer.switchMode( self.__viewer.MODE_INPUT )
        return

    def sessionStopped( self ):
        " Triggered when redirecting session is stopped "
        self.__viewer.switchMode( self.__viewer.MODE_OUTPUT )
        self.__clearButton.setEnabled( True )
        return

    # Mandatory interface part is below

    def getEditor( self ):
        " Provides the editor widget "
        return self.__viewer

    def isModified( self ):
        " Tells if the file is modified "
        return False

    def getRWMode( self ):
        " Tells if the file is read only "
        return "IO"

    def getFileType( self ):
        " Provides the file type "
        return TexFileType

    def setFileType( self, typeToSet ):
        """ Sets the file type explicitly.
            It needs e.g. for .cgi files which can change its type """
        raise Exception( "Setting a file type is not supported by the "
                         "IO console widget" )

    def getType( self ):
        " Tells the widget type "
        return MainWindowTabWidgetBase.IOConsole

    def getLanguage( self ):
        " Tells the content language "
        return "IO console"

    def getFileName( self ):
        " Tells what file name of the widget content "
        return "n/a"

    def setFileName( self, name ):
        " Sets the file name "
        raise Exception( "Setting a file name for IO console "
                         "is not applicable" )

    def getEol( self ):
        " Tells the EOL style "
        return self.__viewer.getEolIndicator()

    def getLine( self ):
        " Tells the cursor line "
        line, _ = self.__viewer.getCursorPosition()
        return int( line )

    def getPos( self ):
        " Tells the cursor column "
        _, pos = self.__viewer.getCursorPosition()
        return int( pos )

    def getEncoding( self ):
        " Tells the content encoding "
        return self.__viewer.encoding

    def setEncoding( self, newEncoding ):
        " Sets the new editor encoding "
        raise Exception( "Setting encoding is not supported by the "
                         "IO console widget" )

    def getShortName( self ):
        " Tells the display name "
        return "IO console"

    def setShortName( self, name ):
        " Sets the display name "
        raise Exception( "Setting short name is not supported by the "
                         "IO console widget" )
