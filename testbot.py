#! /usr/bin/env python
#
# Example program using ircbot.py.
#
# Joel Rosdahl <joel@rosdahl.net>

import string
import gtk
import gtk.gdk
from ircbot import SingleServerIRCBot
from irclib import nm_to_n, irc_lower
import time

class bot(SingleServerIRCBot):
	def __init__(self, main_app, text_buffer, channel, nickname, server, port, fn_data_received):
		SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname,
									self.add_socket_to_main_loop,
									self.remove_socket_from_main_loop,
									self.add_timeout_to_main_loop)
		self.channel = "#"+channel
		self.text_buffer = text_buffer
		self.main_app = main_app
		self.queue = []
		
		self.start()
		self.fn_data_received = fn_data_received

	# Join the channel
	def on_welcome(self, c, e):
		c.join(self.channel)
	
	# Recieved a list of all users currently on the channel
	def on_namreply(self, c, e):
		self.main_app.on_users_received()
	
	# A message is received
	def on_pubmsg(self, c, e):
		print "IRC: "+nm_to_n(e.source())+" "+str(e.arguments()[0])
		self.fn_data_received(nm_to_n(e.source()), str(e.arguments()[0]))

	# User joins
	def on_join(self, c, e):
		self.main_app.on_user_join(nm_to_n(e.source()))
		
	# User leaves
	def on_part(self, c, e):
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

	def check_queue(self):
		if (len(self.queue) > 0 and self.main_app.send_queue > 0):
			message = self.queue.pop(0)
			print "IRC_SENDMSG: "+ message + " "+ str(self.main_app.send_queue)
			self.connection.privmsg(self.channel, message)
			self.main_app.send_queue -= 1

	# Send a message over the network, if the pong count is 0, queue it
	def send_msg(self, message):
		if (self.main_app.send_queue > 0):				
			print "IRC_SENDMSG: "+ message + " "+ str(self.main_app.send_queue)
			self.connection.privmsg(self.channel, message)
			self.main_app.send_queue -= 1
		else:
			print "IRC_SENDMSG: Queued"
			self.queue.append(message)
