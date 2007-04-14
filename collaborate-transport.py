import socket
import logging
import os, os.path

from pyxmpp.all import JID,Iq,Presence,Message,StreamError
from pyxmpp.jabber.all import Client
from pyxmpp.jabber.muc import MucRoomManager, MucRoomHandler

#logger=logging.getLogger()
#logger.addHandler(logging.StreamHandler())
#logger.setLevel(logging.DEBUG)

username = "matt@colyer.name/gedit"
password = u"madack10"

class JabberTransport(Client):
    room_manager = None

    def session_started(self):
        self.stream.send(Presence())
        self.room_manager = MucRoomManager(self.stream)
        self.room_manager.set_handlers()
        channel = self.create_channel("test-collaborate-gedit@conference.jabber.org")
        channel.send("hello world")

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
        if stanza.get_type() == "groupchat" and stanza.get_from() != self.handle_jid:
            print "IN: "+stanza.get_body()

    def send(self, message):
        self.stream.send(Message(to_jid=self.channel_jid, stanza_type="groupchat", body=unicode(message, "utf-8")))

    def user_left(self, user, stanza):
        print "left: "+stanza.get_from().as_utf8()

    def user_joined(self, user,stanza):
        print "joined: "+stanza.get_from().as_utf8()

transport = JabberTransport(jid = JID(username),
                            password = password,
                            auth_methods=["sasl:DIGEST-MD5","digest"])

if os.path.exists("/tmp/gedit-jabber"): os.remove("/tmp/gedit-jabber")
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind("/tmp/gedit-jabber")
s.listen(3)
s.accept()
transport.connect()

while True:
    act = transport.stream.loop_iter(1)
    if act:
        transport.stream.idle()

    datagram = s.recv(1024)
    if not datagram:
        break
    print datagram
    
    s.send("Thank you\n")


server.close()
if os.path.exists("/tmp/gedit-jabber"): os.remove("/tmp/gedit-jabber")
