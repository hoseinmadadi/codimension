# -*- coding: utf-8 -*-
#
# codimension - graphics python two-way code editor and analyzer
# Copyright (C) 2015  Sergey Satskiy <sergey.satskiy@gmail.com>
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

"""
CML utilities
"""

from sys import maxint
from PyQt4.QtGui import QColor
from cdmcf import ( IF_FRAGMENT, FOR_FRAGMENT, WHILE_FRAGMENT, TRY_FRAGMENT,
                    CONTROL_FLOW_FRAGMENT, CLASS_FRAGMENT, FUNCTION_FRAGMENT )


def checkColorRange( value ):
    if value < 0 or value > 255:
        raise Exception( "Invalid color value" )

def readColor( color ):
    """ Four options are supported:
        #hhhhhh             hexadecimal rgb
        #hhhhhhhh           hexadecimal rgb and alpha
        ddd,ddd,ddd         decimal rgb
        ddd,ddd,ddd,ddd     decimal rgb and alpha
    """
    if color.startswith( '#' ):
        color = color[ 1: ]
        length = len( color )
        if length not in [ 6, 8 ]:
            raise Exception( "Invalid hexadecimal color format: #" + color )

        try:
            # The most common case
            r = int( color[ 0:2 ], 16 )
            checkColorRange( r )
            g = int( color[ 2:4 ], 16 )
            checkColorRange( g )
            b = int( color[ 4:6 ], 16 )
            checkColorRange( b )

            if length == 6:
                return QColor( r, g, b )
            a = int( color[ 6:8 ], 16 )
            checkColorRange( a )
            return QColor( r, g, b, a )
        except:
            raise Exception( "Invalid hexadecimal color format: #" + color )

    parts = color.split( ',' )
    length = len( parts )
    if length not in [ 3, 4 ]:
        raise Exception( "Invalid decimal color format: " + color )

    try:
        r = int( parts[ 0 ].strip() )
        checkColorRange( r )
        g = int( parts[ 1 ].strip() )
        checkColorRange( g )
        b = int( parts[ 2 ].strip() )
        checkColorRange( b )

        if length == 3:
            return QColor( r, g, b )
        a = int( parts[ 3 ].strip() )
        checkColorRange( a )
        return QColor( r, g, b, a )
    except:
        raise Exception( "Invalid decimal color format: " + color )



class CMLCommentBase:
    " Base class for all the CML comments "

    def __init__( self, ref = None ):
        self.ref = ref
        return

    def validateRecordType( self, code ):
        if self.ref.recordType != code:
            raise Exception( "Invalid CML comment type. "
                             "Expected: '" + code + "'. Received: '" +
                             self.ref.recordType + "'." )
        return

    def __isSideComment( self, editor ):
        # The only first part needs to be checked
        firstPart = self.ref.parts[ 0 ]
        # Editor has 0-based lines
        leftStripped = editor.text( firstPart.beginLine - 1 ).lstrip()
        return not leftStripped.startswith( firstPart.getContent() )

    def removeFromText( self, editor ):
        " Removes the comment from the code "
        if editor is None:
            return

        isSideComment = self.__isSideComment( editor )

        editor.beginUndoAction()
        oldLine, oldPos = editor.getCursorPosition()

        line = self.ref.endLine
        while line >= self.ref.beginLine:
            if isSideComment:
                raise Exception( "Side CML comments removal has not been implemented yet" )
            else:
                # Editor has 0-based lines
                editor.setCursorPosition( line - 1, 0 )
                editor.deleteLine()
            line -= 1

        editor.setCursorPosition( oldLine, oldPos )
        editor.endUndoAction()
        return


class CMLsw( CMLCommentBase ):
    " Covers the 'if' statement CML SW (switch branches) comments "

    CODE = "sw"

    def __init__( self, ref ):
        CMLCommentBase.__init__( self, ref )
        self.validate()
        return

    def validate( self ):
        self.validateRecordType( CMLsw.CODE )
        CMLVersion.validate( self.ref )
        return

    @staticmethod
    def description():
        " Provides the CML comment description "
        return "The '" + CMLsw.CODE + \
               "' comment is used for 'if' and 'elif' statements " \
               "to switch default branch location i.e. to have the 'No' branch at the right.\n" \
               "Supported properties: none\n\n" \
               "Example:\n" \
               "# cml 1 " + CMLsw.CODE

    @staticmethod
    def generate( pos = 1 ):
        " Generates a complete line to be inserted "
        return " " * (pos -1) + "# cml 1 sw"



class CMLcc( CMLCommentBase ):
    " Covers 'Custom Colors' spec for most of the items "

    CODE = "cc"

    def __init__( self, ref ):
        CMLCommentBase.__init__( self, ref )
        self.bg = None      # background color
        self.fg = None      # foreground color
        self.border = None
        self.validate()
        return

    def validate( self ):
        self.validateRecordType( CMLcc.CODE )
        CMLVersion.validate( self.ref )

        if "background" in self.ref.properties:
            self.bg = readColor( self.ref.properties[ "background" ] )
        if "foreground" in self.ref.properties:
            self.fg = readColor( self.ref.properties[ "foreground" ] )
        if "border" in self.ref.properties:
            self.border = readColor( self.ref.properties[ "border" ] )

        if self.bg is None and self.fg is None and self.border is None:
            raise Exception( "The '" + CMLcc.CODE +
                             "' CML comment does not supply neither "
                             "background nor foreground color nor "
                             "border color" )
        return

    @staticmethod
    def description():
        " Provides the CML comment description "
        return "The '" + CMLcc.CODE + \
               "' comment is used for custom colors of most of " \
               "the graphics items.\n" \
               "Supported properties:\n" \
               "- 'background': background color for the item\n" \
               "- 'foreground': foreground color for the item\n" \
               "- 'border': border color for the item\n" \
               "Color spec formats:\n" \
               "- '#hhhhhh': hexadecimal RGB\n" \
               "- '#hhhhhhhh': hexadecimal RGB + alpha\n" \
               "- 'ddd,ddd,ddd': decimal RGB\n" \
               "- 'ddd,ddd,ddd,ddd': decimal RGB + alpha\n\n" \
               "Example:\n" \
               "# cml 1 " + CMLcc.CODE + " backgound=#f6f4e4 foreground=#000000 border=#ffffff"

    @staticmethod
    def generate( backgound, foreground, border, pos = 1 ):
        " Generates a complete line to be inserted "
        res = " " * (pos -1) + "# cml 1 cc"
        if backgound is not None:
            bg = background.name()
            bgalpha = backgound.alpha()
            if bgalpha != 255:
                bg += hex( bgalpha )[ 2: ]
            res += " background=" + bg
        if foreground is not None:
            fg = foreground.name()
            fgalpha = foreground.alpha()
            if fgalpha != 255:
                fg += hex( fgalpha )[ 2: ]
            res += " foreground=" + fg
        if border is not None:
            brd = border.name()
            brdalpha = border.alpha()
            if brdalpha != 255:
                brd += hex( brdalpha )[ 2: ]
            res += " border=" + brd

        return res


class CMLrt( CMLCommentBase ):
    " Covers 'Replace text' comment "

    CODE = "rt"

    def __init__( self, ref ):
        CMLCommentBase.__init__( self, ref )
        self.text = None
        self.validate()
        return

    def validate( self ):
        self.validateRecordType( CMLrt.CODE )
        CMLVersion.validate( self.ref )

        if "text" in self.ref.properties:
            self.text = self.ref.properties[ "text" ]

        if self.text is None:
            raise Exception( "The '" + CMLrt.CODE +
                             "' CML comment does not supply text" )
        return

    @staticmethod
    def description():
        " Provides the CML comment description "
        return "The '" + CMLrt.CODE + \
               "' comment is used for replacing the text of most of " \
               "the graphics items.\n" \
               "Supported properties:\n" \
               "- 'text': text to be shown instead of the real code\n\n" \
               "Example:\n" \
               "# cml 1 " + CMLrt.CODE + " text=\"Reset the dictionary\""

    @staticmethod
    def generate( txt, pos = 1 ):
        " Generates a complete line to be inserted "
        res = " " * (pos -1) + "# cml 1 rt"
        if txt is not None:
            res += " text=\"" + txt.replace( '"', '\\"' ) + "\""
        return res


class CMLVersion:
    " Describes the current CML version "

    VERSION = 1     # Current CML version
    COMMENT_TYPES = { CMLsw.CODE: CMLsw,
                      CMLcc.CODE: CMLcc,
                      CMLrt.CODE: CMLrt }

    def __init__( self ):
        return

    @staticmethod
    def validate( cmlComment ):
        if cmlComment.version > CMLVersion.VERSION:
            raise Exception( "The CML comment version " +
                             str( cmlComment.version ) +
                             " is not supported. Max supported version is " +
                             str( CMLVersion.VERSION ) )

    @staticmethod
    def find( cmlComments, cmlType ):
        for comment in cmlComments:
            if hasattr( comment, "CODE" ):
                if comment.CODE == cmlType.CODE:
                    return comment
        return None

    @staticmethod
    def getType( cmlComment ):
        try:
            return CMLVersion.COMMENT_TYPES[ cmlComment.recordType ]
        except KeyError:
            return None

    @staticmethod
    def validateCMLComments( item ):
        """ Walks recursively all the items in the control flow and validates
            the CML comments. Replaces the recognized CML comments from the module
            with their higher level counterparts.
            Returns back a list of warnings. """
        warnings = []
        if hasattr( item, "leadingCMLComments" ):
            warnings += CMLVersion.validateCMLList( item.leadingCMLComments )

        # Some items are containers
        if item.kind == IF_FRAGMENT:
            for part in item.parts:
                warnings += CMLVersion.validateCMLComments( part )
        elif item.kind in [ FOR_FRAGMENT, WHILE_FRAGMENT ]:
            if item.elsePart:
                warnings += CMLVersion.validateCMLComments( item.elsePart )
        elif item.kind == TRY_FRAGMENT:
            if item.elsePart:
                warnings += CMLVersion.validateCMLComments( item.elsePart )
            if item.finallyPart:
                warnings += CMLVersion.validateCMLComments( item.finallyPart )
            for part in item.exceptParts:
                warnings += CMLVersion.validateCMLComments( part )

        if item.kind in [ CONTROL_FLOW_FRAGMENT,
                          CLASS_FRAGMENT, FUNCTION_FRAGMENT ]:
            if item.docstring:
                warnings += CMLVersion.validateCMLList( item.docstring.leadingCMLComments )
                warnings += CMLVersion.validateCMLList( item.docstring.sideCMLComments )


        if hasattr( item, "sideCMLComments" ):
            warnings += CMLVersion.validateCMLList( item.sideCMLComments )

        if hasattr( item, "suite" ):
            for nestedItem in item.suite:
                warnings += CMLVersion.validateCMLComments( nestedItem )
        return warnings

    @staticmethod
    def validateCMLList( comments ):
        """ Validates the CML comments in the provided list.
            Internal usage only. """
        warnings = []
        if comments:
            count = len( comments )
            for index in xrange( count ):
                cmlComment = comments[ index ]
                cmlType = CMLVersion.getType( cmlComment )
                if cmlType:
                    try:
                        highLevel = cmlType( cmlComment )
                        comments[ index ] = highLevel
                    except Exception, exc:
                        line = cmlComment.parts[ 0 ].beginLine
                        pos = cmlComment.parts[ 0 ].beginPos
                        warnings.append( (line, pos,
                                          "Invalid CML comment: " + str( exc )) )
                else:
                    line = cmlComment.parts[ 0 ].beginLine
                    pos = cmlComment.parts[ 0 ].beginPos
                    warnings.append( (line, pos,
                                      "CML comment type '" +
                                      cmlComment.recordType +
                                      "' is not supported") )
        return warnings

    @staticmethod
    def getFirstLine( comments ):
        # The list may contain raw comments and high level comments
        line = maxint
        if comments:
            if hasattr( comments[ 0 ], "ref" ):
                # High level CML comment
                return comments[ 0 ].ref.parts[ 0 ].beginLine
            # Raw CML comment
            if comments[ 0 ].parts:
                return comments[ 0 ].parts[ 0 ].beginLine
        return line

