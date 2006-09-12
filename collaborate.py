#!/usr/bin/env python
#
# Copyright (C) 2004 Matthew Colyer
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
# This file contains the GUI and associated functions for collaborate.
#

import gtk
import gtk.glade

from xml.dom import minidom
from xml.dom.minidom import Document

import urllib

import collab_irc
import collab_transform

VERSION_STRING="Collaborate Prototype 3"
COLORS = { 0 : "red", 1 : "orange", 2 : "yellow", 3 : "green", 4 : "blue"}

class collaborate:
	def __init__(self):
		# Set the debug to true
		self.debug = 1
		
		# Load the interface file
		self.widgets = gtk.glade.XML("collaborate.glade")    
		self.widgets.signal_autoconnect (self)
		
		# Create a buffer
		self.screen_buffer = gtk.TextBuffer()

		# Connect the buffer
		self.widgets.get_widget("text_view").set_buffer(self.screen_buffer)
		self.widgets.get_widget("text_view").set_property("editable", False)
		
		# Connect events to buffer
		self.insert_signal = self.screen_buffer.connect("insert-text", 
													  self.on_insert, None)
		self.delete_signal = self.screen_buffer.connect("delete-range",
													  self.on_delete, None)
		self.screen_buffer.connect("mark-set", self.on_cursor_move, None)
		
		# Initialize callback pointers
		self.dialog_open_response = None
		self.dialog_save_response = None
		
		# Initialize the key_timer
		self.key_timer = None
		
		# Timeout between keystrokes to determine a pause
		self.user_pause_time = 4000
		
		# Timeout before a broadcast is assumed to be unanswered
		self.timeout = 3000
		
		# Create a dictionary of dicitionaries for users
		self.collaborators = {}
	
		# Create a dictionary of dictionaries for successors
		self.succession = {}
		
		# Create a group operations queue
		self.group_operations_queue = []
		
		# Create a queue for the commands which a user types without a pause
		self.user_pause_queue = []
		
		# This client's unique ID
		self.unique_id = 0
		
		# This client's clock
		self.clock = 0

		# This client's role: echoer, master or none
		self.role =""
		
		# last issued unique ID
		self.last_unique_id = 0		
		
		# Limitation in order to make sure that messages do not get sent
		# one after the other
		self.send_queue = 1
		
		self.clear_session()		
		self.create_session()
		
	def main(self):
		gtk.main()
		
	###########################################################################
	# User interface callbacks
	###########################################################################
	
	def connection_settings_close(self, widget, data=None):
		if (self.debug):
			print "connection_settings_close"
		
		# Just close here instead of using the quit action because nothing has 
		# been started
		gtk.main_quit()
		
	def connection_settings_ok(self, widget, data=None):
		if (self.debug):
			print "connection_settings_ok"
		
		self.widgets.get_widget("window_connect").hide()
		
		# Get the information out of the widget
		self.server = self.widgets.get_widget("entry_server").get_text()
		self.port = int(self.widgets.get_widget("entry_port").get_text())
		self.username = self.widgets.get_widget("entry_username").get_text()
		self.channel = self.widgets.get_widget("entry_channel").get_text()
		
		# Create the connection
		self.network_connection = collab_irc.bot(self,
											  self.channel, self.username,
											  self.server, self.port, 
											  self.on_data_receive)
		
		self.widgets.get_widget("window_main").show()
	
	def file_new(self, widget, data=None):
		if (self.debug):
			print "file_new"
			
		self.clear_session()
		self.create_session()

	def file_open(self, widget, data=None):
		if (self.debug):
			print "file_open"
	
		self.widgets.get_widget("dialog_file_open").show()

		if (self.dialog_open_response):
			self.widgets.get_widget("dialog_file_open").disconnect(self.dialog_open_response)
		self.dialog_open_response = self.widgets.get_widget("dialog_file_open").connect("response", self.file_open_response, None)
		
	def file_open_response(self, widget, response, data=None):
		if (self.debug):
			print "file_open_response"
	
		if (response == gtk.RESPONSE_NONE or response == gtk.RESPONSE_CANCEL):
			self.widgets.get_widget("dialog_file_open").hide()			
	
		elif (response == gtk.RESPONSE_OK):
			self.widgets.get_widget("dialog_file_open").hide()
			
			# FIXME: Find a way to block the insert signal but still append
			# items to the document tree

			self.clear_session()
			self.create_session()
			
			self.current_filename = self.widgets.get_widget("dialog_file_open").get_filename()
			
			self.widgets.get_widget("text_view").set_data("editable", False)
			self.read_file()
			self.widgets.get_widget("text_view").set_data("editable", True)

	def file_save(self, widget, data=None):
		if (self.debug):
			print "file_save"
		
		# Check if the file has already been saved
		if (self.current_filename):
			self.save_file()
		else:
			self.widgets.get_widget("dialog_file_save").show()	
			
		if (self.dialog_save_response):
			self.widgets.get_widget("dialog_file_save").disconnect(self.dialog_save_response)
		self.widgets.get_widget("dialog_file_save").connect("response", self.file_save_response, None)
	
	def file_save_as(self, widget, data=None):
		if (self.debug):
			print "file_save_as"
		
		self.widgets.get_widget("dialog_file_save").show()
		
		if (self.dialog_save_response):
			self.widgets.get_widget("dialog_file_save").disconnect(self.dialog_save_response)
		self.widgets.get_widget("dialog_file_save").connect("response", self.file_save_response, None)

	def file_save_response(self, widget, response, data=None):
		if (self.debug):
			print "file_save_response"
		
		if (response == gtk.RESPONSE_NONE or response == gtk.RESPONSE_CANCEL):
			self.widgets.get_widget("dialog_file_save").hide()	
		
		elif (response == gtk.RESPONSE_OK):
			self.widgets.get_widget("dialog_file_save").hide()
			
			self.current_filename = self.widgets.get_widget("dialog_file_save").get_filename()
			
			self.widgets.get_widget("text_view").set_data("editable", False)
			self.save_file()
			self.widgets.get_widget("text_view").set_data("editable", True)
	
	def file_session_open(self, widget, data=None):
		if (self.debug):
			print "file_session_open"	
		
		self.widgets.get_widget("dialog_file_open").show()
		
		if (self.dialog_open_response):
			self.widgets.get_widget("dialog_file_open").disconnect(self.dialog_open_response)
		self.widgets.get_widget("dialog_file_open").connect("response", self.file_session_open_response, None)

	def file_session_open_response(self, widget, response, data=None):
		if (self.debug):
			print "file_session_open_response"
			
		if (response == gtk.RESPONSE_NONE or response == gtk.RESPONSE_CANCEL):
			self.widgets.get_widget("dialog_file_open").hide()			
		
		elif (response == gtk.RESPONSE_OK):
			self.widgets.get_widget("dialog_file_open").hide()
			
			self.clear_session()
			self.create_session()
			
			self.current_session_filename = self.widgets.get_widget("dialog_file_open").get_filename()
			
			self.widgets.get_widget("text_view").set_data("editable", False)
			self.parse_file()
			self.widgets.get_widget("text_view").set_data("editable", True)

	def file_session_save(self, widget, data=None):
		if (self.debug):
			print "file_session_save"	
		
		self.widgets.get_widget("dialog_file_save").show()
		
		if (self.dialog_save_response):
			gtk.disconnect(self.dialog_save_response)
		self.widgets.get_widget("dialog_file_save").connect("response", self.file_session_save_response, None)

	def file_session_save_response(self, widget, response, data=None):
		if (self.debug):
			print "file_session_save_response"
			
		if (response == gtk.RESPONSE_NONE or response == gtk.RESPONSE_CANCEL):
			self.widgets.get_widget("dialog_file_save").hide()			
		
		elif (response == gtk.RESPONSE_OK):
			self.widgets.get_widget("dialog_file_save").hide()
			
			self.current_session_filename = self.widgets.get_widget("dialog_file_save").get_filename()
			
			self.widgets.get_widget("text_view").set_data("editable", False)
			self.session_to_file()
			self.widgets.get_widget("text_view").set_data("editable", True)

	# FIXME: Implement these
	def edit_cut(self, widget, data=None):
		print "edit_cut"
		
	def edit_copy(self, widget, data=None):
		print "edit_copy"
		
	def edit_paste(self, widget, data=None):
		print "edit_paste"
		
	###########################################################################
	# Actions
	###########################################################################
	
	def read_file(self):
		file = open(self.current_filename, "r")
		self.screen_buffer.set_text(file.read())
		file.close()
		self.screen_buffer.set_modified(False)
	
	def parse_file(self):
		#FIXME: minidom doesn't handle spaces well
		document = minidom.parse(self.current_session_filename)
		self.parse_command(document.documentElement)
		
		# Add the old tree to the current tree		
		for element in document.documentElement.childNodes:
			self.root_node.appendChild(element.cloneNode(False))
			
		document.unlink()
		self.screen_buffer.set_modified(False)
	
	def save_file(self):	
		file = open(self.current_filename, "w")
		start, end = self.screen_buffer.get_bounds()
		file.write(self.screen_buffer.get_text(start, end))
		file.close()
		self.screen_buffer.set_modified(False)

	def session_to_file(self):
		file = open(self.current_session_filename, "w")
		file.write(self.session.toxml())
		file.close()

	def clear_session(self):
		self.screen_buffer.set_text("")	
		self.screen_buffer.set_modified(False)
		self.current_filename = None
		self.current_session_filename = None
		self.cursor_last_pos = 0
		
		# It might not exist at this point
		try:
			self.session.unlink()
		except:
			pass
			
		self.root_node = None
		
	def create_session(self):
		self.session = Document()
		self.root_node = self.session.createElement("session")
		self.session.appendChild(self.root_node)

	def set_key_timer(self):
		if (len(self.user_pause_queue) == 0):
			# Notify the user
			self.widgets.get_widget("label_buffer_notification").set_markup("<span background=\"red\">Buffer Not Empty</span>")
	
			# Notify the network
			xmlmsg_command = self.session.createElement("command")
			xmlmsg_command.setAttribute("role", self.role)
			xmlmsg_command.setAttribute("source", self.username)
			
			xmlmsg_activity = self.session.createElement("activity")
			xmlmsg_command.appendChild(xmlmsg_activity)
			
			self.network_connection.queued_commands.append(xmlmsg_command)
			self.network_connection.flush_queue()
		
		# Reset the timer
		if (self.key_timer):
			gtk.timeout_remove(self.key_timer)
			self.key_timer = gtk.timeout_add(self.user_pause_time, self.on_user_pause)
		else:
			self.key_timer = gtk.timeout_add(self.user_pause_time, self.on_user_pause)

	def execute_message(self, command_to_execute):
		undo_buffer = []
		
		# Undo all operations until EO -> O
		history_buffer = self.root_node.childNodes
		history_buffer.reverse()
		
		for executed_command in history_buffer:
			order = self.compare_total_ordering(command_to_execute, executed_command)
			if (order == 1):
				break
			elif (order == -1):
				self.root_node.childNodes.remove(executed_command)
				undo_buffer.append(executed_command)
		
		self.got_algorithm(command_to_execute)
		
		print "TRANSFORM: "+command_to_execute.toxml()
		
		# Transform the operations and reapply them
		if (len(undo_buffer) != 0):
			for command in undo_buffer:
				original_undo_buffer.append(operation.cloneNode(False))
				
			reverse_original_undo_buffer = original_undo_buffer
			reverse_original_undo_buffer.reverse()
			
			inclusion_transformation(undo_buffer, command_to_execute)
			for i in range(1, len(undo_buffer)):
				list_exclusion_transformation([undo_buffer[i]], reverse_original_undo_buffer[0:i-1])
				list_inclusion_transformation([undo_buffer[i]], undo_buffer[0:i-1])
			
			for command in undo_buffer:
				#reapply
				pass
		
	def got_algorithm(self, command_to_execute):
		first_indep_operation = ""
		causal_pre_operations = []
		k = 0
		
		for executed_command in self.root_node.childNodes:
			vector_clock_a = eval(command_to_execute.getAttribute("timestamp"))
			vector_clock_b = eval(command_to_execute.getAttribute("timestamp"))

			if (self.compare_vector_clocks(vector_clock_a, vector_clock_b) == 0):
				first_indep_operation = executed_command
				break
			k += 1
		
		if (first_indep_operation == ""):
			return [command_to_execute]
		
		for executed_command in self.root_node.childNodes[k+1:]:
			vector_clock_a = eval(command_to_execute.getAttribute("timestamp"))
			vector_clock_b = eval(command_to_execute.getAttribute("timestamp"))
			
			if (self.compare_vector_clocks(vector_clock_a, vector_clock_b) == -1):
				causal_pre_operations.append(executed_command)
				break 
				
		if (len(causal_pre_operations) == 0):
			site_id = command_to_execute.getAttribute("site")
			timestamp = command_to_execute.getAttribute("timestamp")
			
			for operation in command_to_execute.childNodes:
				operation.setAttribute("site", site_id)
				operation.setAttribute("timestamp", timestamp)
				collab_transform.list_inclusion_transformation([operation], self.root_node.childNodes[k:])
		else:
			reverse_of_casual_pre_operations = causal_pre_operations
			reverse_of_casual_pre_operations.reverse()
			
			for operation in casual_pre_operations:
				executed_operations.append(operation.cloneNode(False))
			
			reverse_of_executed_operations = executed_operations
			reverse_of_executed_operations.reverse()
			
			list_execlusion_transformation([casual_pre_operations[0]], reverse_of_casual_pre_operations[0:1])
			for i in range(1,len(reverse_of_casual_pre_operations)):
				list_execlusion_transformation([casual_pre_operations[i]], reverse_of_executed_operations[0:i-1])
				list_inclusion_transformation([casual_pre_operations[i]],  casual_pre_operations[0:i-1])
			list_exclusion_transformation([command_to_execute], reverse_of_casual_pre_operations)
			list_inclusion_transformation([command_to_execute], executed_operations)
		
	def parse_message(self, root_element, action="apply"):
		acknowledged = False
		
		if (root_element.tagName == "command"):
			self.parse_message_command(root_element, acknowledged, action)
			
		elif (root_element.tagName == "session"):
			if (self.role == "Echoer"):
				self.send_command("echo")
				acknowledged = True
			
			# If this session isn't intended for this client skip processing
			# In the future this should go away because of private messaging
			if (root_element.getAttribute("destination") != self.username and root_element.getAttribute("destination") != "file"):
				return
			
			# Feed through a session as if it were a series of commmands
			for command in root_element:
				self.parse_message_command(command, acknowledged)
			
		elif (root_element.tagName == "collaborators"):
			# If this user information isn't intended for this client skip processing
			if (root_element.getAttribute("destination") != self.username and root_element.getAttribute("destination") != "file"):
				return	
				
			self.parse_message_collaborators(root_element)
			
	def parse_message_command(self, root_element, acknowledged, action="apply"):
		remote_role = root_element.getAttribute("role")
		remote_source = root_element.getAttribute("source")
		append_to_tree = False
		
		# The id does not exist after a broadcast message is sent.
		# If a echo is heard from the echoer then it will throw
		# a key error. FIXME: This should be prevented but for now this will
		# work
		try:
			remote_id = self.collaborators[remote_source]['id']
		except KeyError:
			remote_id = ""
	 
	 	if (root_element.getAttribute("timestamp")):
		 	remote_vc = eval(root_element.getAttribute("timestamp"))
		 	self.collaborators[remote_source]["clock"] = remote_vc[remote_id]
		 	print "SETTING REMOTE CLOCK: "+str(self.collaborators[remote_source]["clock"])
		 	self.clock = max(self.clock, remote_vc[remote_id])
		 	print "MAX:"+str(self.clock)
	 
		for element in root_element.childNodes:
			
			if (self.debug > 1):
				print "PARSING: " + element.tagName
	
			# If the message needs a reply to keep the conversation going...
			if (self.role == "Echoer" and element.tagName != "ack" and not acknowledged):
				self.send_command("echo")
				acknowledged = True
			elif (self.role == "Master" and remote_role == "Echoer" and element.tagName != "ack" and not acknowledged ):
				self.send_command("echo")
				acknowledged = True
				
			# Decide which type of message it is and handle it accordingly
			if (element.tagName == "current"):
				if (self.role == "Master" and self.root_node.hasChildNodes()):
					self.send_session(remote_source)
					acknowledged = True
					
			elif (element.tagName == "insert"):
				if (action == "apply"):
					pos = int(element.getAttribute("position"))
					string = urllib.unquote(element.getAttribute("string"))
					text_buffer_pos = self.screen_buffer.get_iter_at_offset(pos)

					self.screen_buffer.handler_block(self.insert_signal)
					self.screen_buffer.insert_with_tags_by_name(text_buffer_pos, string, "remote-"+str(remote_id))
					self.screen_buffer.handler_unblock(self.insert_signal)
					
					element.setAttribute("site", str(remote_id))
					element.setAttribute("timestamp", str(remote_vc))
					
					self.root_node.appendChild(element.cloneNode(False))
				elif (action == "unapply"):
					start = self.screen_buffer.get_iter_at_offset(int(element.getAttribute("position")))
					end = self.screen_buffer.get_iter_at_offset(int(element.getAttribute("position")) + int(element.getAttribute("length")))
				
					self.screen_buffer.handler_block(self.delete_signal)
					self.screen_buffer.delete(start, end)
					self.screen_buffer.handler_unblock(self.delete_signal)
					
			elif (element.tagName == "delete"):
				if (action == "apply"):
					start = self.screen_buffer.get_iter_at_offset(int(element.getAttribute("position")))
					end = self.screen_buffer.get_iter_at_offset(int(element.getAttribute("position")) + int(element.getAttribute("length")))
				
					self.screen_buffer.handler_block(self.delete_signal)
					element.setAttribute("removed-string", self.screen_buffer.get_text(start,end))
					self.screen_buffer.delete(start, end)
					self.screen_buffer.handler_unblock(self.delete_signal)
					
					element.setAttribute("site", str(remote_id))
					element.setAttribute("timestamp", str(remote_vc))
					
					self.root_node.appendChild(element.cloneNode(False))
				elif (action == "unapply"):
					pos = int(element.getAttribute("position"))
					string = urllib.unquote(element.getAttribute("string"))
					text_buffer_pos = self.screen_buffer.get_iter_at_offset(pos)
					
					self.screen_buffer.handler_block(self.delete_signal)
					self.screen_buffer.insert_with_tags_by_name(text_buffer_pos, string, "remote-"+str(remote_id))
					self.screen_buffer.handler_unblock(self.delete_signal)								

			elif (element.tagName == "broadcast"):
				version = urllib.unquote(element.getAttribute("version"))

				# Handle version mismatch
				if (version != VERSION_STRING):
					if (self.role == "Master"):
						#FIXME: Send an error message
						pass
					else:				
						return
				
				if (self.role == "Master"):
					self.send_collaborators(remote_source)
			
		self.widgets.get_widget("text_view").set_property("editable", True)
		
	def parse_message_collaborators(self, root_element):
		remote_role = root_element.getAttribute("role")
		remote_source = root_element.getAttribute("source")
		
		# Cancel the broadcast timeout, we are not the master.
		gtk.timeout_remove(self.broadcast_timeout)
		
		# Iterate through the users
		for element in root_element.childNodes:
			if (element.tagName == "source"):
				iterative_source = urllib.unquote(element.getAttribute("source"))
				iterative_id = int(element.getAttribute("id"))
				iterative_clock = int(element.getAttribute("clock"))
				
				# Set the last_unique id to the highest value
				if (iterative_source > self.last_unique_id):
					self.last_unique_id = iterative_source
				
				if (iterative_source != self.username):
					self.succession[iterative_source] = iterative_id
					self.collaborators[iterative_source] = {'id' : iterative_id, 'clock' : iterative_clock}
					tag = self.screen_buffer.create_tag("remote-"+str(iterative_id))
					tag.set_property("background", COLORS[iterative_id])
				else:
					self.unique_id = iterative_id
					
		# If queue is one then you are echoer
		if (len(self.succession) == 1):
			self.role = "Echoer"
		elif (len(self.succession) > 1):
			pass
		
		self.send_command("current")
					
		self.widgets.get_widget("text_view").set_property("editable", True)

	def stablize_group_operations_queue(self):
		if (self.debug):
			print "stablize_group_operations_queue"
		
		stable_queue = []
		
		for message in self.group_operations_queue:
			remote_source = message.getAttribute("source")
			
			# The id does not exist after a broadcast message is sent.
			# If a echo is heard from the echoer then it will throw
			# a key error. FIXME: This should be prevented but for now this will
			# work
			try:
				remote_site = self.collaborators[remote_source]['id']
			except KeyError:
				pass
				
			remote_clock = eval(message.getAttribute("timestamp"))
			
			if (self.is_stable(remote_site, remote_clock)):
				stable_queue.append(message)
			
		for message in stable_queue:
			self.group_operations_queue.remove(message)
			self.execute_message(message)
			self.parse_message(message)
		
		print "GO: "+str(self.group_operations_queue)	
		
		if (len(stable_queue) > 0):
			self.stablize_group_operations_queue()

	def quit(self, widget, data=None):		
		self.network_connection.disconnect(VERSION_STRING)
		gtk.main_quit()
		
	###########################################################################	
	# Events
	###########################################################################
		
	def on_cursor_move(self, textbuffer, iter, textmark, data=None):
		# FIXME: The sending of curor movements has been disabled.
		# It has to be determined whether they should go into
		# the buffer or not. It may confuse the user if it does
		# go into the buffer
		
		# If the id has already been sent return
		if (self.cursor_last_pos == iter.get_offset()): 
			return
		
		# Create the XML element
		xmlmsg_cursor = self.session.createElement("cursor")
		xmlmsg_cursor.setAttribute("position",  str(iter.get_offset()))
		
		# Append it to the internal command queue
		#self.user_pause_queue.append(xmlmsg_cursor)
		
		if (self.debug > 1):
			print xmlmsg_cursor.toprettyxml(indent="   ")
			
		# Track the last broadcasted position
		self.cursor_last_pos = iter.get_offset()
		
		# Set a timer on the cursor move
		# FIXME: It will reset the timer from the keypress.
		#        The timing won't be exact, but this is a hack
		#if (self.key_timer):
		#	gtk.timeout_remove(self.key_timer)
		#	self.key_timer = gtk.timeout_add(self.user_pause_time, self.on_user_pause)
		#else:
		#	self.key_timer = gtk.timeout_add(self.user_pause_time, self.on_user_pause)

	def on_insert(self, widget, position, new_text, text_length, data=None):
		# Set the Key press timer
		self.set_key_timer()
		
		# Create the XML element
		xmlmsg_insert = self.session.createElement("insert")
		xmlmsg_insert.setAttribute("string", urllib.quote(new_text))
		
		# Send the starting position 
		xmlmsg_insert.setAttribute("position",  str(position.get_offset()))		
		
		# Add string length to position in order to prevent
		#  the sending of a cursor message
		self.cursor_last_pos = position.get_offset() + len(new_text)

		# Append it to the internal queue
		self.user_pause_queue.append(xmlmsg_insert)
		
		if (self.debug > 1):
			print xmlmsg_insert.toprettyxml(indent="   ")
 		
	def on_delete(self, widget, start_pos, end_pos, data=None):
		# Set the Key press timer
		self.set_key_timer()
		
		# Create the XML element
		xmlmsg_delete = self.session.createElement("delete")
		xmlmsg_delete.setAttribute("length", str(end_pos.get_offset()-start_pos.get_offset()))
		
		# If the position has not already been sent in a seperate tag
		if (self.cursor_last_pos != start_pos.get_offset()):
			xmlmsg_delete.setAttribute("position",  str(start_pos.get_offset()))		
			self.cursor_last_pos = start_pos.get_offset()

		# Append it to the internal queue
		self.user_pause_queue.append(xmlmsg_delete)
		
		if (self.debug > 1):
			print xmlmsg_delete.toprettyxml(indent="   ")
			
	def on_user_pause(self, data=None):
		print "on_user_pause"

		#Initialize Variables
		cursor_position = None
		last_included_cursor_position = None
		virtual_text_buffer = {}
		command_elements = []
		xmlmsg = None
		
		# Combine the commands
		for element in self.user_pause_queue:			
			# Insert the command's effects into the virtual_text_buffer
			if (element.tagName == "insert"):
				pos = int(element.getAttribute("position"))
				cursor_position = pos+1
				string = urllib.unquote(element.getAttribute("string"))
				for character in string:
					virtual_text_buffer[pos] = character 
					pos += 1
			# Delete from the virtual_text_buffer or mark it with a -1	
			elif (element.tagName == "delete"):
				pos = int(element.getAttribute("position"))
				length = int(element.getAttribute("length"))
				for a in range(length):
					if (virtual_text_buffer.has_key(pos)):
						del virtual_text_buffer[pos]
					else:
						virtual_text_buffer[pos] = -1
					pos += 1
			# Just take the last known position of the cursor	
			elif (element.tagName == "cursor"):
				cursor_position = int(element.getAttribute("position"))
		
		# Clear the queue
		self.user_pause_queue = []
		
		# Take the virtual text buffer and break it into segments which
		# are continous with same command
		
		last_position = 0
		
		sorted_virtual_text_buffer = virtual_text_buffer.items()
		sorted_virtual_text_buffer.sort()
		
		for position, character in sorted_virtual_text_buffer:
			if (self.debug > 1):
				print "CHAR: "+character+":"+str(position)
				
			# Delete case
			if (character == -1):				
				# If there is a break in continunity or type of command
				if ((xmlmsg and xmlmsg.tagName != "delete") or (xmlmsg and last_position+1 != position)):
					command_elements.append(xmlmsg)
					last_included_cursor_position = int(xmlmsg.getAttribute("length"))+int(xmlmsg.getAttribute("position"))
					xmlmsg = self.session.createElement("delete")
					xmlmsg.setAttribute("position", str(position))
					xmlmsg.setAttribute("length", "0")
				# This is the intialization case
				elif (not xmlmsg):
					xmlmsg = self.session.createElement("delete")
					xmlmsg.setAttribute("position", str(position))
					xmlmsg.setAttribute("length", "0")
					
				# Add one to the length of the deleted range
				xmlmsg.setAttribute("length", str(int(xmlmsg.getAttribute("length")) + 1))

			# Otherwise it is an insert
			else:					
				# If there is a break in continunity or type of command
				if ((xmlmsg and xmlmsg.tagName != "insert") or (xmlmsg and last_position+1 != position)):
					xmlmsg.setAttribute("string", urllib.quote(xmlmsg.getAttribute("string")))
					command_elements.append(xmlmsg)
					last_included_cursor_position = len(xmlmsg.getAttribute("string"))+int(xmlmsg.getAttribute("position"))
					
					print xmlmsg.toxml()
					print len(xmlmsg.toxml())
					
					xmlmsg = self.session.createElement("insert")
					xmlmsg.setAttribute("position", str(position))
					xmlmsg.setAttribute("string", "")
				# This is the initialization case
				elif (not xmlmsg):
					xmlmsg = self.session.createElement("insert")
					xmlmsg.setAttribute("position", str(position))
					xmlmsg.setAttribute("string", "")
				
				# Add the character to the inserted string
				xmlmsg.setAttribute("string", xmlmsg.getAttribute("string") + character)

			last_position = position
		
		# There will always be one message left when the above loop
		# finishes, unless there are only cursor commands. 
		# Make sure we grab it and throw it in the queue
		if (xmlmsg):
			if (xmlmsg.tagName == "insert"):
				xmlmsg.setAttribute("string", urllib.quote(xmlmsg.getAttribute("string")))
				last_included_cursor_position = len(xmlmsg.getAttribute("string"))+int(xmlmsg.getAttribute("position"))
			elif (xmlmsg.tagName == "delete"):
				last_included_cursor_position = int(xmlmsg.getAttribute("length"))+int(xmlmsg.getAttribute("position"))
			command_elements.append(xmlmsg)
		
		# Compile a cursor tag
		if (cursor_position and cursor_position != last_included_cursor_position):
			xmlmsg_cursor = self.session.createElement("cursor")
			xmlmsg_cursor.setAttribute("position",  str(cursor_position))
			command_elements.append(xmlmsg_cursor)
		
		# Increment the local clock
		self.clock += 1
		
		xmlmsg_command = self.session.createElement("command")
		xmlmsg_command.setAttribute("role", self.role)
		xmlmsg_command.setAttribute("source", self.username)
		xmlmsg_command.setAttribute("timestamp", str(self.create_timestamp()))
		
		# Append the commands to the session and create a command packet		
		for command in command_elements :
			xmlmsg_command.appendChild(command.cloneNode(False))

			command.setAttribute("timestamp", str(self.create_timestamp()))
			command.setAttribute("site", str(self.unique_id))
			
			self.root_node.appendChild(command.cloneNode(False))
				
		# Update the screen output to user
		if (len(self.user_pause_queue) == 0):
			self.widgets.get_widget("label_buffer_notification").set_markup("<span background=\"green\">Buffer Empty</span>")
		
		if (len (command_elements) != 0 and len(self.collaborators) != 0):
			self.network_connection.queued_commands.append(xmlmsg_command)
			self.network_connection.flush_queue()

	def on_broadcast_timeout(self):
		if (self.debug):
			print "Broadcast timed out"
	
		# If no one has responded, I must be the master
		self.role = "Master"	
		self.unique_id = 0
		self.last_unique_id = self.unique_id
		
		self.widgets.get_widget("text_view").set_property("editable", True)		

	
	###########################################################################	
	# Network Events
	###########################################################################
	
	def on_user_join(self, user):
		print "on_user_join"

		if (user != self.username):
			self.last_unique_id += 1
			self.collaborators[user] = {'id' : self.last_unique_id, 'clock' : 0}
			tag = self.screen_buffer.create_tag("remote-"+str(self.last_unique_id))
			tag.set_property("background", COLORS[self.last_unique_id])
		else:
			# Send out broadcast signal
			xmlmsg_command = self.session.createElement("command")
			xmlmsg_command.setAttribute("source", self.username)
			
			xmlmsg_broadcast = self.session.createElement("broadcast")
			xmlmsg_broadcast.setAttribute("version", VERSION_STRING)
			xmlmsg_command.appendChild(xmlmsg_broadcast)
	
			self.network_connection.queued_commands.append(xmlmsg_command)
			self.network_connection.flush_queue()
	
			# Set timer
			self.broadcast_timeout = gtk.timeout_add(self.timeout, self.on_broadcast_timeout)
			
		
	def on_user_leave(self, user):
		print "on_user_leave"		
		if (user != self.username):
			# Ignore the error if the user isn't in the list
			try:
				del self.collaborators[user]
			except KeyError:
				pass
				
			try:
				del self.succession[user]
			except KeyError:
				pass				
				
			print self.collaborators
			print self.succession
			
			if (len(self.succession) == 0):
				self.role = "Master"	
			elif (len(self.succession) == 1):
				self.role = "Echoer"
	
	def on_users_received(self):
		pass	


	def on_data_receive(self, source, data):
		print "on_data_receive"
		
		group_operation = False
		
		self.send_queue += 1
		self.network_connection.flush_queue()
		
		if (self.debug > 1):
			print "send_queue: " + str(self.send_queue)
			
		# Parse the data
		try:
			received_document = minidom.parseString(data)
		except:
			print "Invalid message data received"
		
		for element in received_document.documentElement.childNodes:
			if (element.tagName == "insert" or element.tagName == "delete" or element.tagName == "cursor"):
				group_operation = True

		if (group_operation):
			self.group_operations_queue.append(received_document.documentElement)
			self.stablize_group_operations_queue()
		else:
			self.parse_message(received_document.documentElement)

	###########################################################################	
	# Utility functions
	###########################################################################
	def create_timestamp(self):
		timestamp = {self.unique_id : self.clock}
		for user,data in self.collaborators.iteritems():
			timestamp[data['id']] = data['clock']
		print self.collaborators
		return timestamp	

	def find_collaborator_from_site(self, collaborator_id):
		for collaborator,collaborator_data in self.collaborators.iteritems():
			if (collaborator_data["id"] == collaborator_id):
				return collaborator
	
	def compare_total_ordering(self, message_a, message_b):
		message_a_site = message_a.getAttribute("site")
		message_b_site = message_b.getAttribute("site")
		message_a_vc = eval(message_a.getAttribute("timestamp"))
		print message_b.toxml()
		message_b_vc = eval(message_b.getAttribute("timestamp"))
		
		a_clock_sum = 0
		b_clock_sum = 0
		
		# Compare
		for collaborator_id,clock in message_b_vc.iteritems():
			# FIXME: This index may not exist if the node drops off
			a_clock_sum += message_a_vc[collaborator_id]
			b_clock_sum += clock

		print "COMPARISON: "+str(message_a_vc)+" "+str(message_b_vc)

		if (a_clock_sum < b_clock_sum):
			# Remote message precedes current state
			return -1
		elif (a_clock_sum > b_clock_sum):
			# Remote message follows present state
			return 1
		else:
			if (message_a_site > message_b_site):
				return 1
			elif (message_a_site < message_b_site):
				return -1
			return 0
			
	def compare_vector_clocks(self, vector_clock_a, vector_clock_b):
		a_clock_sum = 0
		b_clock_sum = 0
		
		# Compare
		for collaborator_id,clock in vector_clock_b.iteritems():
			# FIXME: this index may not exist if the node drops off
			a_clock_sum += vector_clock_a[collaborator_id]
			b_clock_sum += clock

		if (a_clock_sum < b_clock_sum):
			# Remote message precedes current state
			return -1
		elif (a_clock_sum > b_clock_sum):
			# Remote message follows present state
			return 1
		else:
			# Message is orthagonal to current state
			return 0
				
	def is_stable(self, site, vector_clock):
		remote_collaborator = self.find_collaborator_from_site(site)
		local_clock = self.collaborators[remote_collaborator]['clock']

		for clock,i in vector_clock.iteritems():
			# Condition 1
			# 0 <= i <= site, remote_clock <= VC[i]
			if (i < site):
				if (clock > self.collaborators[remote_collaborator]['clock']):
					return False

			# Condition 2
			# site < i < N, remote_clock <= VC[i] + 1	
			elif (i > site):
				if (clock > (self.collaborators[remote_collaborator]['clock']+1)):
					return False
					
		return True
	
	###########################################################################	
	# Message functions
	###########################################################################	
	def send_command(self, command):
		xmlmsg_command = self.session.createElement("command")
		xmlmsg_command.setAttribute("role", self.role)
		xmlmsg_command.setAttribute("source", self.username)
		xmlmsg_command.setAttribute("id", str(self.unique_id))
		
		xmlmsg_ack = self.session.createElement("ack")
		xmlmsg_command.appendChild(xmlmsg_ack)
		
		self.network_connection.queued_commands.append(xmlmsg_command)
		self.network_connection.flush_queue()

	def send_session(self, remote_source):
		xmlmsg_session = self.session.createElement("session")
		xmlmsg_session.setAttribute("destination", remote_source)

		for command in self.root_node.childNodes:
			xmlmsg_session.appendChild(command.cloneNode(False))		
			
		self.network_connection.queued_commands.append(xmlmsg_session)
		self.network_connection.flush_queue()
		
	def send_collaborators(self, remote_source):
		xmlmsg_collaborators = self.session.createElement("collaborators")
		xmlmsg_collaborators.setAttribute("role", self.role)
		xmlmsg_collaborators.setAttribute("source", self.username)
		xmlmsg_collaborators.setAttribute("destination", remote_source)

		# Add self
		xmlmsg_source = self.session.createElement("source")
		xmlmsg_source.setAttribute("source", urllib.quote(self.username))
		xmlmsg_source.setAttribute("id", urllib.quote(str(self.unique_id)))
		xmlmsg_source.setAttribute("clock", urllib.quote(str(self.clock)))
		xmlmsg_collaborators.appendChild(xmlmsg_source)

		for user,data in self.collaborators.iteritems():
			xmlmsg_source = self.session.createElement("source")
			xmlmsg_source.setAttribute("source", urllib.quote(user))
			xmlmsg_source.setAttribute("id", str(data['id']))
			xmlmsg_source.setAttribute("clock", str(data['clock']))
			xmlmsg_collaborators.appendChild(xmlmsg_source)
		
		self.network_connection.queued_commands.append(xmlmsg_collaborators)
		self.network_connection.flush_queue()
		
if __name__ == "__main__":
    collaborate = collaborate()
    collaborate.main()
