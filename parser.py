#!/usr/bin/env python
# Matthew Colyer
# 1/21/2004

import gtk
from xml.sax import saxutils

class sax_handler(saxutils.DefaultHandler):

	# Initialize the class
	def __init__(self, textbuffer):
		self.textbuffer = textbuffer
		
		self.position = 0
		
	def startElement(self, name, attrs):	
		if (name == "insert"):
			# FIXME: Need this at a later point
			#attrs.get('source', "")
			self.position = self.textbuffer.get_iter_at_offset(int(attrs.get('position', "")))
			self.textbuffer.insert_with_tags(self.position, attrs.get('string', ""))
			
		elif (name == "delete"):
			start = self.textbuffer.get_iter_at_offset(int(attrs.get('position', "")))
			end = self.textbuffer.get_iter_at_offset(int(attrs.get('position', "")) + int(attrs.get('length', "")))
			self.textbuffer.delete(start, end)

		elif (name == "cursor"):
			print name+" element"

class error_handler:
    """Basic interface for SAX error handlers. If you create an object
    that implements this interface, then register the object with your
    Parser, the parser will call the methods in your object to report
    all warnings and errors. There are three levels of errors
    available: warnings, (possibly) recoverable errors, and
    unrecoverable errors. All methods take a SAXParseException as the
    only parameter."""

    global SGMLSyntaxError
    SGMLSyntaxError = "SGML syntax error"

    def error(self, exception):
        "Handle a recoverable error."
        sys.stderr.write ("Error: %s\n" % exception)

    def fatalError(self, exception):
        "Handle a non-recoverable error."
        sys.stderr.write ("Fatal error: %s\n" % exception)
        raise SGMLSyntaxError

    def warning(self, exception):
        "Handle a warning."
        sys.stderr.write ("Warning: %s\n" % exception)
