#!/usr/bin/env python
# Matthew Colyer
# 1/21/2004

import gtk
import gtk.glade
from xml.dom import minidom
from xml.dom.minidom import Document
from xml.sax import make_parser
from xml.sax.handler import feature_namespaces
from xml.sax.handler import feature_validation
import testbot
import urllib
import time

VERSION_STRING="Collaborate Prototype 1"

class collaborate:
	# User interface callbacks
	def connection_settings_close(self, widget, data=None):
		print "connection_settings_close"
		gtk.main_quit()
		
	def connection_settings_ok(self, widget, data=None):
		print "connection_settings_ok"
		
		self.widgets.get_widget('window_connect').hide()
		
		self.server = self.widgets.get_widget("entry_server").get_text()
		self.port = int(self.widgets.get_widget("entry_port").get_text())
		self.username = self.widgets.get_widget("entry_username").get_text()
		self.password = self.widgets.get_widget("entry_password").get_text()
		self.channel = self.widgets.get_widget("entry_channel").get_text()
		
		self.network_connection = testbot.bot(self, self.text_buffer, self.channel, self.username, self.server, self.port, self.on_data_receive)
		
		# FIXME: things can go very wrong if the user tries to enter text before the master/echoer state is decided
		
		self.widgets.get_widget('window_main').show()
	
	def file_new(self, widget, data=None):
		print "file_new"
		self.text_buffer.set_text("")	
		self.dirty = False

	def file_open(self, widget, data=None):
		print "file_open"	
		self.widgets.get_widget('dialog_file_open').show()
		self.widgets.get_widget('dialog_file_open').connect("response", self.file_open_response, None)
		
	def file_open_response(self, widget, response, data=None):
		print "file_open_response"
		if (response == gtk.RESPONSE_NONE or response == gtk.RESPONSE_CANCEL):
			self.widgets.get_widget('dialog_file_open').hide()			
		elif (response == gtk.RESPONSE_OK):
			# Hide the dialog
			self.widgets.get_widget('dialog_file_open').hide()
			
			# Read the file
			file = open(self.widgets.get_widget('dialog_file_open').get_filename(), "r")
			self.text_buffer.set_text(file.read())
			file.close()

	#FIXME: Implement
	def file_save(self, widget, data=None):
		print "file_save"
	
	#FIXME: Implement
	def file_save_as(self, widget, data=None):
		print "file_save_as"

	def file_session_open(self, widget, data=None):
		print "file_session_open"	
		self.widgets.get_widget('dialog_file_open').show()
		
		# FIXME: Does it double connect?
		self.widgets.get_widget('dialog_file_open').connect("response", self.file_session_open_response, None)

	def file_session_open_response(self, widget, response, data=None):
		print "file_session_open_response"
		if (response == gtk.RESPONSE_NONE or response == gtk.RESPONSE_CANCEL):
			self.widgets.get_widget('dialog_file_open').hide()			
		elif (response == gtk.RESPONSE_OK):
			# Hide the dialog
			self.widgets.get_widget('dialog_file_open').hide()
			
			# Clear the interface
			self.file_new(None)
			
			# Clear the session
			self.create_session()
			
			# FIXME: Read the file

	# FIXME: Do I need the next three functions?
	def edit_cut(self, widget, data=None):
		print "edit_cut"
		
	def edit_copy(self, widget, data=None):
		print "edit_copy"
		
	def edit_paste(self, widget, data=None):
		print "edit_paste"
    
	def quit(self, widget, data=None):
		if (self.debug):
			file = open("output", "w")
			file.write(self.session.toprettyxml(indent="  "))
			file.close()
			
		self.network_connection.disconnect(VERSION_STRING)
		gtk.main_quit()
	
	# Events
	def on_change(self, editable, data=None):
		#print "on_change"
		self.dirty = True
		
	def on_cursor_move(self, textbuffer, iter, textmark, data=None):
		# If the id has already been sent return
		if (self.cursor_last_pos == iter.get_offset()): 
			return
		
		# Create the XML element
		xmlmsg_cursor = self.session.createElement("cursor")
		xmlmsg_cursor.setAttribute("source", self.position)
		xmlmsg_cursor.setAttribute("position",  str(iter.get_offset()))
		
		# Append it to the XML Document
		self.rootnode.appendChild(xmlmsg_cursor)
		
		# Send it to the network
		if (len(self.collaborators) > 0):
			self.network_connection.send_msg(xmlmsg_cursor.toxml())
		
		#if (self.debug):
		#	print xmlmsg_cursor.toprettyxml(indent="   ")
			
		# Track the last broadcasted position
		self.cursor_last_pos = iter.get_offset()

	def on_insert(self, widget, position, new_text, text_length, data=None):
		# Create the XML element
		xmlmsg_insert = self.session.createElement("insert")
		xmlmsg_insert.setAttribute("source", self.position)
		xmlmsg_insert.setAttribute("string", urllib.quote(new_text))
		
		# Send the starting position 
		xmlmsg_insert.setAttribute("position",  str(position.get_offset()))		
		
		# Add string length to position in order to prevent
		#  the sending of a cursor message
		self.cursor_last_pos = position.get_offset() + len(new_text)
		
		# Append it to the XML Document
		self.rootnode.appendChild(xmlmsg_insert)

		# Send it to the network
		if (len(self.collaborators) > 0):
			self.network_connection.send_msg(xmlmsg_insert.toxml())
		
		#if (self.debug):
		#	print xmlmsg_insert.toprettyxml(indent="   ")
 		

	def on_delete(self, widget, start_pos, end_pos, data=None):
		# Create the XML element
		xmlmsg_delete = self.session.createElement("delete")
		xmlmsg_delete.setAttribute("source", self.position)
		xmlmsg_delete.setAttribute("length", str(end_pos.get_offset()-start_pos.get_offset()))
		
		# If the position has not already been sent in a seperate tag
		if (self.cursor_last_pos != start_pos.get_offset()):
			xmlmsg_delete.setAttribute("position",  str(start_pos.get_offset()))		
			self.cursor_last_pos = start_pos.get_offset()
		
		# Append it to the XML Document
		self.rootnode.appendChild(xmlmsg_delete)

		# Send it to the network
		if (len(self.collaborators) > 0):
			self.network_connection.send_msg(xmlmsg_delete.toxml())
		
		#if (self.debug):
		#	print xmlmsg_delete.toprettyxml(indent="   ")

	#Network Events
	def on_user_join(self, user):
		print "on_user_join"
		if (user != self.username):
			self.collaborators.append({"name" : user})
		
	def on_user_leave(self, user):
		print "on_user_leave"		
		if (user != self.username):
			for current_user in self.collaborators:
				if (current_user['name'] == user):
					self.collaborators.remove(current_user)
					return
		
	def on_users_received(self):
		#Get a list of people in the channel stuff in queue
		users = self.network_connection.get_users()					
		for user in users:
			if (user != self.username):
				self.succession.append({"name" : user})
				self.collaborators.append({"name" : user})		

		# If queue is empty then master
		if (len(self.succession) == 0):
			self.position = "Master"		
		# If queue is one then you are echoer
		elif (len(self.succession) == 1):
			self.position = "Echoer"
			
			# Increase the send_queue because an echoer must be able to send twice
			self.send_queue += 1
			
			xmlmsg_current = self.session.createElement("current")
			self.network_connection.send_msg(xmlmsg_current.toxml())
		# Otherwise you are just chillin
		else:
			xmlmsg_current = self.session.createElement("current")
			self.network_connection.send_msg(xmlmsg_current.toxml())
		
		self.widgets.get_widget("text_view").set_property("editable", True)		


	def on_data_receive(self, source, data):
		print "on_data_receive"
		
		self.send_queue += 1
		print "send_queue: " + str(self.send_queue)
		self.network_connection.check_queue()
		
		# Parse the data
		try:
			received_document = minidom.parseString(data)
			# Process the data
			# FIXME: Add algorithim
			self.parse_tag(received_document.documentElement)
		
			# Add it to the current document tree
			self.rootnode.appendChild(received_document.documentElement)	
		except:
			if (self.debug):
				print "Invalid message data received"
	
	def parse_tag(self, element):
		print "parse_tag"
		
		#if (self.debug):
		#	print element.tagName

		# If the message needs a reply to keep the conversation going...
		if (self.position == "Echoer" and element.tagName != "pong"):
			xmlmsg_pong = self.session.createElement("pong")
			self.network_connection.send_msg(xmlmsg_pong.toxml())
		elif (self.position == "Master" and element.getAttribute('source') == "Echoer"):
			xmlmsg_pong = self.session.createElement("pong")
			self.network_connection.send_msg(xmlmsg_pong.toxml())
		
		# Decide which type of message it is and handle it accordingly
		if (element.tagName == "insert"):
			pos = int(element.getAttribute('position'))
			string = urllib.unquote(element.getAttribute('string'))
			
			text_buffer_pos = self.text_buffer.get_iter_at_offset(pos)
			self.text_buffer.handler_block(self.insert_signal)
			self.text_buffer.insert_with_tags_by_name(text_buffer_pos, string, "remote")
			self.text_buffer.handler_unblock(self.insert_signal)
		
		elif (element.tagName == "delete"):
			start = self.text_buffer.get_iter_at_offset(int(element.getAttribute('position')))
			end = self.text_buffer.get_iter_at_offset(int(element.getAttribute('position')) + int(element.getAttribute('length')))
			self.text_buffer.handler_block(self.delete_signal)
			self.text_buffer.delete(start, end)
			self.text_buffer.handler_unblock(self.delete_signal)
			
		elif (element.tagName == "current"):
			if (self.position == "Master" and self.rootnode.hasChildNodes()):
				for command in self.rootnode.childNodes:
					self.network_connection.send_msg(command.toxml())
	
	def create_session(self):
		# Create XML document
		self.session = Document()
		self.rootnode = self.session.createElement("session")
		self.session.appendChild(self.rootnode)
	
	def __init__(self):
		# Set the debug to true
		self.debug = True
		
		# Load the interface file
		self.widgets = gtk.glade.XML("collaborate.glade")    
		self.widgets.signal_autoconnect (self)
		
		# Create a buffer
		self.text_buffer = gtk.TextBuffer()

		# Connect it
		self.widgets.get_widget("text_view").set_buffer(self.text_buffer)
		self.widgets.get_widget("text_view").set_property("editable", False)
		
		# Connect events to buffer
		self.text_buffer.connect("changed", self.on_change, None)
		self.insert_signal = self.text_buffer.connect("insert-text", self.on_insert, None)
		self.delete_signal = self.text_buffer.connect("delete-range", self.on_delete, None)
		self.text_buffer.connect("mark-set", self.on_cursor_move, None)
		
		# Create a list of dicitionaries for users
		self.collaborators = []
	
		# Create a list of dictionaries for succession
		self.succession = []
		
		self.send_queue = 1
		
		# Setup some colors
		tag = self.text_buffer.create_tag("remote")
		tag.set_property('background', 'blue')
		tag.set_property('rise', True)
		tag.set_property('rise', -12)
		
		
		self.dirty = False
		self.cursor_last_pos = 0
		
		self.create_session()
		
	def main(self):
		gtk.main()

if __name__ == "__main__":
    collaborate = collaborate()
    collaborate.main()
