#
# Orginially an example program using ircbot.py. Now it is an
# interfacing class between collaborate and the irc stack.
#
# Joel Rosdahl <joel@rosdahl.net>
# Heavily Modified by Matthew Colyer <linuxcoder@colyer.org>

import gtk
import gtk.gdk

from xml.dom.minidom import Document

from ircbot import SingleServerIRCBot
from irclib import nm_to_n

import re

# The maximum in the RFC is stated to be 512, however this includes a
# length of the nickname. Even then some irc servers don't seem to play nice
# it is set at a safe value to make sure things don't dropped.
MAXIMUM_MESSAGE_LENGTH=400

class bot(SingleServerIRCBot):
	def __init__(self, main_app, channel, nickname, server, port, fn_data_received):
		
		# Invoke the IRC bot
		SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname,
									self.add_socket_to_main_loop,
									self.remove_socket_from_main_loop,
									self.add_timeout_to_main_loop)

		# Set the channel name to the irc standard
		self.channel = "#"+channel
		
		# Pointer to the collaborate instance, this should really go away in the future
		self.main_app = main_app
		
		# This is the only interface which we should use to the collaborate instance
		self.return_data = fn_data_received
		
		# The list of commands sent from the collaborate instance waiting to be sent
		self.queued_commands = []
		
		# Buffers used to hold oversized messages
		self.current_send_buffer = ""
		self.current_recv_buffer = ""
		
		self.start()

	# Internal function which is called when any message has been recieved
	def flush_queue(self):
		if ((self.main_app.send_queue > 0 or (self.main_app.role != "" and self.main_app.send_queue >= 0))):

			# If a command is already over the wire
			if (self.current_send_buffer != ""):
				# Check if the message still needs to be split
				if (len(self.current_send_buffer) > MAXIMUM_MESSAGE_LENGTH):
					message = self.current_send_buffer[0:MAXIMUM_MESSAGE_LENGTH]
					self.current_send_buffer = self.current_send_buffer[MAXIMUM_MESSAGE_LENGTH:]
				else:
					message = self.current_send_buffer
					self.current_send_buffer = ""
			elif (len(self.queued_commands) > 0):
				message = self.queued_commands.pop(0).toxml()
				# Check to see if the message needs split
				if (len(message) > MAXIMUM_MESSAGE_LENGTH):
					self.current_send_buffer = message[MAXIMUM_MESSAGE_LENGTH:]
					message = message[:MAXIMUM_MESSAGE_LENGTH]
			else:
				return

			print "IRC_SENDMSG: "+ message + " "+ str(self.main_app.send_queue)
			
			self.connection.privmsg(self.channel, message)
			self.main_app.send_queue = 0
	
	# A message is received
	def on_pubmsg(self, c, e):
		print "IRC: "+nm_to_n(e.source())+" "+str(e.arguments()[0])
		
		message = str(e.arguments()[0])

		# Determine whether there is a lead tag or not
		# Limitation 1) the tag has to fit in the min message size.
		# If it doesn't then you should lay off of the drugs...
		# Limitation 2) the tag can not have an extra > in it in the username field
		open_tag_regexp = re.compile("<(\w+)[^>]*>")
		
		# Is there a partial message already being recieved?
		if (self.current_recv_buffer != ""):
			self.current_recv_buffer += message
			
			if (self.main_app.role == "Echoer"):
				# Return XML, Ugly
				command = "<command role=\"Echoer\" source=\""+str(self.main_app.username)+"\">"
				command += "<ack/>"
				command += "</command>"
				print "IRC_SENDMSG: "+ command + " "+ str(self.main_app.send_queue)
				self.connection.privmsg(self.channel, command)
				self.main_app.send_queue = 0
			
			# Find the opening tag and the closing tag
			match = open_tag_regexp.match(self.current_recv_buffer)	
			close_tag_regexp = re.compile("</"+match.group(1)+">")
			match = close_tag_regexp.search(message)
			
			if (match):
				self.return_data(nm_to_n(e.source()), self.current_recv_buffer)
				self.current_recv_buffer = ""
				#FIXME: Verify that this is working... (old FIXME Pop the lock)
				self.main_app.widgets.get_widget("text_view").set_editable(True)
				self.main_app.widgets.get_widget("statusbar").pop(1)
				#FIXME: This is a hack!
				self.main_app.widgets.get_widget("text_view").modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("#FFFFFF"))
		else:
			# Find the opening tag
			match = open_tag_regexp.match(message)	
			
			# There should always be a match
			if (not match):			
				print "Invalid data recieved"
				return	
			
			# Find the closing tag
			close_tag_regexp = re.compile("</"+match.group(1)+">")
			match = close_tag_regexp.search(message)
			
			if (match):
				self.return_data(nm_to_n(e.source()), message)
				self.main_app.widgets.get_widget("text_view").set_editable(True)
				self.main_app.widgets.get_widget("statusbar").pop(1)
				#FIXME: This is a hack!
				self.main_app.widgets.get_widget("text_view").modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("#FFFFFF"))
			else:
				self.current_recv_buffer = message
				
				self.main_app.widgets.get_widget("statusbar").push(1, "Data transaction, data input frozen")
				self.main_app.widgets.get_widget("text_view").set_editable(False)
				self.main_app.widgets.get_widget("text_view").modify_base(gtk.STATE_NORMAL, gtk.gdk.color_parse("#CCCCCC"))
				
				if (self.main_app.role == "Echoer"):
					# Return XML, Ugly
					command = "<command role=\"Echoer\" source=\""+str(self.main_app.username)+"\">"
					command += "<ack/>"
					command += "</command>"
					print "IRC_SENDMSG: "+ command + " "+ str(self.main_app.send_queue)
					self.connection.privmsg(self.channel, command)
					self.main_app.send_queue = 0

	# Join the channel
	def on_welcome(self, c, e):
		c.join(self.channel)
	
	# Recieved a list of all users currently on the channel. Occurs only on a
	# channel join.
	def on_namreply(self, c, e):
		self.main_app.on_users_received()

	# User joins
	def on_join(self, c, e):
		self.main_app.on_user_join(nm_to_n(e.source()))
		
	# User leaves
	def on_part(self, c, e):
		self.main_app.on_user_leave(nm_to_n(e.source()))
	
	# FIXME user quits or client quits?	
	def on_quit(self, c, e):
		self.main_app.on_user_leave(nm_to_n(e.source()))
	
	# Return a list of users in the first channel
	def get_users(self):
		chname, chobj = self.channels.items()[0]
		return chobj.users()
	
	# Add socket polling to the main GTK loop
	def add_socket_to_main_loop(self, socket):
		self.socket = socket
		self.socket_fd = gtk.input_add(socket, gtk.gdk.INPUT_READ, self.on_socket_data)
		
	# Remove socket polling to the main GTK loop
	def remove_socket_from_main_loop(self, socket):
		self.socket = None
		gtk.input_remove(self.socket_fd)

    # Create timeout in the GTK loop
	def add_timeout_to_main_loop(self, interval):
		gtk.timeout_add(interval, self.on_timeout)

	# Receive call from gtk_main_loop and dispatch
	def on_socket_data(self, source, condition):
		sockets = [self.socket]
		self.ircobj.process_data(sockets)
		return 1
    
	# Receive call from a gtk timer and dispatch
	def on_timeout(self):
		self.ircobj.process_timeout()
		return 0

