import select
import socket
import logging
import os, os.path
import time

from pyxmpp.all import JID,Iq,Presence,Message,StreamError
from pyxmpp.jabber.all import Client
from pyxmpp.jabber.muc import MucRoomManager, MucRoomHandler

#logger=logging.getLogger()
#logger.addHandler(logging.StreamHandler())
#logger.setLevel(logging.DEBUG)

username = "matt@colyer.name/gedit"
password = u"madack10"

channel = None
transport = None
conn = None

events = []

class JabberTransport(Client):
    room_manager = None
    is_connected = False

    def session_started(self):
        self.stream.send(Presence())
        self.room_manager = MucRoomManager(self.stream)
        self.room_manager.set_handlers()
        self.is_connected = True

    def create_channel(self, channel):
        jabber_channel = JabberChannel(self.stream, channel, 1)
        self.room_manager.join(JID(channel), 1, jabber_channel, history_maxstanzas=0)
        return jabber_channel

    def idle(self):
        Client.idle(self)
        if self.session_established:
            pass
            #target=JID("jajcus",s.jid.domain)
            #self.stream.send(Message(to_jid=target,body=unicode("asdf","utf-8")))

class JabberChannel(MucRoomHandler):
    channel_jid = None
    handle_jig = None
    stream = None
    
    def __init__(self, stream, channel, handle):
        self.channel_jid = JID(channel)
        self.stream = stream
        self.handle_jid = JID("%s/%s" % (channel, handle))
    
    def message_received(self, user, stanza):
        global conn
        if stanza.get_type() == "groupchat" and stanza.get_from() != self.handle_jid:
            print "IN: "+stanza.get_body()
            conn.sendall(stanza.get_body())

    def send(self, message):
        self.stream.send(Message(to_jid=self.channel_jid, stanza_type="groupchat", body=unicode(message, "utf-8")))

    def user_left(self, user, stanza):
        print "LEFT: "+stanza.get_from().as_utf8()

    def user_joined(self, user,stanza):
        if stanza.get_from() != self.handle_jid:
            print "JOINED: "+stanza.get_from().as_utf8()

def handle_data(data):
    global transport
    if data == "<connect/>":
        transport = JabberTransport(jid = JID(username),
                                    password = password,
                                    auth_methods=["sasl:DIGEST-MD5","digest"])
        transport.connect()

    elif data == "<open-channel/>":
        def open_channel():
            global channel
            if transport.is_connected:
                channel = transport.create_channel("test-collaborate-gedit@conference.jabber.org")
                return True
            else:
                return False
        events.append(open_channel)
    
    elif data == "<close-channel/>":
        pass
    
    elif data == "<disconnect/>":
        pass
    
    else:
        channel.send(data)
    
# Start the pipe to allow the gedit plugin to talk to us
if os.path.exists("/tmp/gedit-jabber"): os.remove("/tmp/gedit-jabber")
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind("/tmp/gedit-jabber")
s.listen(1)

# Wait until we get a connection
conn, address = s.accept()

while True:
    # Poll the socket
    in_list, out_list, err_list = select.select([conn], [], [], 0)
    if len(in_list) > 0:
        data = in_list[0].recv(2048)
        if len(data) == 0: break
        print data.split('\n')[:-1]
        for command in data.split('\n')[:-1]:
            handle_data(command)

    # Service the jabber connection if it has been connected
    if transport is not None:
        transport.stream.loop_iter(1)
        #if act:
        #    transport.stream.idle()

    # Execute pending events
    to_remove = []
    for i, event in enumerate(events):
        val = event()
        if val: to_remove.append(i)
    for i in to_remove:
        events.pop(i)

conn.close()
if os.path.exists("/tmp/gedit-jabber"): os.remove("/tmp/gedit-jabber")
