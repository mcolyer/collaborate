"""
Author: Matthew Colyer <linuxcoder@colyer.org>

Inspiration/copying came from the GNOME live pages about the gedit plugins.

"""

import copy
import sys
import gtk
import gobject
import gconf
import gnomekeyring
import gtk.glade
import socket
import re
import select
import os.path
import time
import xml.dom.minidom
import xml.dom.ext
import md5

GCONF_KEY_BASE = '/apps/gedit-2/plugins/collaborate'
GCONF_KEY_JABBER_SERVER = GCONF_KEY_BASE + '/jabber_server'

GLADE_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'collaborate.glade'))

SOCKET_PATH = '/tmp/gedit-jabber' 
TRANSPORT_COMMAND = os.path.abspath(os.path.join(os.path.dirname(__file__), 'collaborate-transport.py'))

try:
    import gedit
    
    class CollaboratePlugin(gedit.Plugin):
        def __init__(self):
            gedit.Plugin.__init__(self)
            self._instances = {}

        def activate(self, window):
            self._instances[window] = CollaborateWindowHelper(self, window)
        
        def deactivate(self, window):
            self._instances[window].deactivate()
            del self._instances[window]

        def update_ui(self, window):
            self._instances[window].update_ui()

        def is_configurable(self):
            return true
        
        def create_configure_dialog(self):
            preferences = CollaboratePreferenceWindow(self)
            return preferences.window

        def get_server(self):
            return gconf.client_get_default().get_string(GCONF_KEY_JABBER_SERVER)

        def _get_auth(self):
            server = self.get_server()

            # Query the keyring
            try:
                results = gnomekeyring.find_items_sync(gnomekeyring.ITEM_NETWORK_PASSWORD, {'server': server, 'protocol': 'jabber'})
            except gnomekeyring.DeniedError:
                # No results were returned
                self._user = ""
                self._password = ""
            else:
                #FIXME: This is hack, we are only allowing one account to a specific server
                self._user = results[0].attributes['user']
                self._password = results[0].secret

        def get_user(self):
            self._get_auth()
            return self._user

        def get_password(self):
            self._get_auth()
            return self._password

    class CollaboratePreferenceWindow:
        def __init__(self, plugin):
            self._glade_tree = gtk.glade.XML(GLADE_FILE)
            self._keyring = gnomekeyring.get_default_keyring_sync()
            self._plugin = plugin

            # Attach the signals
            dic = {'on_preferences_response' : self.on_preferences_response,
                   'on_server_unfocus' : self.on_server_unfocus}
            self._glade_tree.signal_autoconnect(dic)

            # Load the gconf value of the server
            server = self._plugin.get_server()
            if server is not None:
                self._glade_tree.get_widget('server').set_text(server)

            # Access the keyring
            self.retrieve_keyring_data(server)
            
            # Create the gtk Window
            self.window = self._glade_tree.get_widget('preferences')

        #
        # Helper functions
        #
        def retrieve_keyring_data(self, server):
            # If the server is blank don't bother loading keyring data
            if server != None and server != '':
                return

            # Query the keyring
            try:
                results = gnomekeyring.find_items_sync(gnomekeyring.ITEM_NETWORK_PASSWORD, {'server': server, 'protocol': 'jabber'})
            except gnomekeyring.DeniedError:
                # No results were returned
                user = ""
                password = ""
            else:
                #FIXME: This is hack, we are only allowing one account to a specific server
                user = results[0].attributes['user']
                password = results[0].secret
        
            # Update the interface
            self._glade_tree.get_widget('user').set_text(user)
            self._glade_tree.get_widget('password').set_text(password)

        def set_keyring_data(self, server, user, password):
            #FIXME: Should we remove old keyring entries?

            # Check to make sure whether we need to update the keyring entry or not
            try:
                results = gnomekeyring.find_items_sync(gnomekeyring.ITEM_NETWORK_PASSWORD, {'server': server, 'user': user, 'protocol': 'jabber'})
            except gnomekeyring.DeniedError:
                # The entry doesn't exist
                gnomekeyring.item_create_sync(self._keyring,
                                                  gnomekeyring.ITEM_NETWORK_PASSWORD,
                                                  '',
                                                  {'server': server, 'user': user, 'authtype': 'password', 'protocol': 'jabber'},
                                                  password,
                                                  True)
            else:
                #FIXME: This is hack, we are only allowing one account to a specific server
                # The entry exists, make sure it isn't identical
                if password != results[0].secret:
                    gnomekeyring.item_create_sync(self._keyring,
                                                  gnomekeyring.ITEM_NETWORK_PASSWORD,
                                                  '',
                                                  {'server': server, 'user': user, 'authtype': 'password', 'protocol': 'jabber'},
                                                  password,
                                                  True)
        #
        # Callbacks
        #
        def on_server_unfocus(self, widget, event, data=None):
            server = self._glade_tree.get_widget('server').get_text()
            orig_server = gconf.client_get_default().get_string(GCONF_KEY_JABBER_SERVER)
            if orig_server != server:
                self.retrieve_keyring_data(server)

        def on_preferences_response(self, dialog, response_id, data=None):
            if response_id == gtk.RESPONSE_OK:
                server = self._glade_tree.get_widget('server').get_text()
                gconf.client_get_default().set_string(GCONF_KEY_JABBER_SERVER, server)

                user = self._glade_tree.get_widget('user').get_text()
                password = self._glade_tree.get_widget('password').get_text()
                
                self.set_keyring_data(server, user, password)

            dialog.hide()

    
    class CollaborateWindowHelper:
        def __init__(self, plugin, window):
            self._window = window
            self._plugin = plugin
            self._documents = []

            self._insert_menu()
            
        def deactivate(self):
            self._remove_menu()

            self._window = None
            self._plugin = None
            self._action_group = None

            for document in documents:
                document.deactivate()

            del documents

        def _insert_menu(self):
            manager = self._window.get_ui_manager()

            # Create a new action group
            self._action_group = gtk.ActionGroup('CollaboratePluginActions')
            self._action_group.add_actions([('Collaborate', None, 'Share document',
                                             None, 'Share the document',
                                             self.on_share_document_activate)])

            manager.insert_action_group(self._action_group, -1)
            
            # Merge the UI
            ui_str = """<ui>
                  <menubar name="MenuBar">
                    <menu name="ToolsMenu" action="Tools">
                      <placeholder name="ToolsOps_2">
                        <menuitem name="Collaborate" action="Collaborate"/>
                      </placeholder>
                    </menu>
                  </menubar>
                </ui>
                """
            self._ui_id = manager.add_ui_from_string(ui_str)

        def _remove_menu(self):
            manager = self._window.get_ui_manager()

            manager.remove_ui(self._ui_id)

            manager.remove_action_group(self._action_group)

            manager.ensure_update()

        def update_ui(self):
            self._action_group.set_sensitive(self._window.get_active_document() != None)

        def on_share_document_activate(self, action):
            doc = self._window.get_active_document()
            if not doc:
                return
            self._documents.append(Document(self._plugin, doc))


    class Document:
        _geditDocument = None

        def __init__(self, plugin, doc):
            self._plugin = plugin
            server = self._plugin.get_server()
            user = self._plugin.get_user()
            password = self._plugin.get_password()

            self._transport = Transport.create(server, user, password)
            self._transport.join("")
            self._geditDocument = doc
            self._geditDocument.connect('insert-text', self.insert)
            self._geditDocument.connect('delete-range', self.delete)
        
        def deactivate(self):
            pass

        def execute(self, command):
            if isinstance(command, InsertOperation):
                self._geditDocument.insert(self._geditDocument.get_iter_at_offset(command.p), command.s)
            elif isinstance(command, DeleteOperation):
                self._geditDocument.delete(self._geditDocument.get_iter_at_offset(command.p), self._geditDocument.get_iter_at_offset(command.p+command.l))

        def insert(self, textbuffer, iter, text, length, data=None):
            self._transport.send(self.hash(), str(InsertOperation(text, iter.get_offset()))+"\n")
        
        def delete(self, textview, start, end, data=None):
            offset = start.get_offset()
            length = end.get_offset() - offset
            self._transport.send(self.hash(), str(DeleteOperation(length, offset)))

        def hash(self):
            return md5.new(this._geditDocument.get_uri()).digest()
    
    class Transport:
        _transport = None
        _documents = []

        @staticmethod
        def create(server, user, password, document):
            if Transport._transport is None:
                Transport._transport = Transport(server, user, password)
            Transport._documents[document.hash()] = document

            return Transport._transport

        def __init__(self, server, user, password):
            self._transport_stdin, self._transport_stdout = os.popen2(TRANSPORT_COMMAND)
            
            time.sleep(0.1)
            
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(SOCKET_PATH)
            
            gobject.idle_add(self.handle_socket)
            
            self._doc = xml.dom.minidom.Document()
            
            self.connect(server, user, password)
            
            
        def connect(self, server, user, password):
            command = self._doc.createElement("connect")
            command.setAttribute("server", server)
            command.setAttribute("user", user)
            command.setAttribute("password", password)

            self.socket.sendall("%s\n" % xml.dom.ext.Print(command))

        def join(self, document_id):
            command = self._doc.createElement("open-channel")
            command.setAttribute("document_id", document_id)

            self.socket.sendall("%s\n" % xml.dom.ext.Print(command))
        
        def send(self, document_id, message):
            command = self._doc.createElement("message")
            message = self._doc.createTextNode(message)
            #TODO: Nest node with channel info
            self.socket.sendall(message)

        def leave(self, document_id):
            command = self._doc.createElement("close-channel")
            command.setAttribute("document_id", document_id)

            self.socket.sendall("%s\n" % xml.dom.ext.Print(command))

        def disconnect(self):
            command = self._doc.createElement("disconnect")

            self.socket.sendall("%s\n" % xml.dom.ext.Print(command))
    
        def quit(self):
            command = self._doc.createElement("quit")

            self.socket.sendall("%s\n" % xml.dom.ext.Print(command))

        def handle_socket(self):
            #TODO: Need to reverse map the list of documents to a specific document
            in_list, out_list, err_list = select.select([self.socket], [], [], 0.01)
            if len(in_list) > 0:
                for connection in in_list:
                    data = connection.recv(2048)
                    self.execute(Operation.parse(data))

            return True
 
        def deactivate(self):
            self.quit()
            self._transport_stdin.close()
            self._transport_stdout.close()
            self.socket.close()
 
except:
    print "WARNING: No Gedit environment"

class Operation:
    @staticmethod
    def parse(string):
        insert_re = re.compile("Insert\[\"([^\"]+)\",([0-9]+)\]")
        delete_re = re.compile("Delete\[\"([^\"]+)\",([0-9]+)\]")
        if insert_re.match(string):
            text, position = insert_re.match(string).groups()
            position = int(position)
            return InsertOperation(text, position)
        elif delete_re.match(string):
            length, position = delete_re.match(string).groups()
            length = int(length)
            position = int(position)
            return DeleteOperation(length, position)

    def is_insert(self):
        return False
    
    def is_delete(self):
        return false
    
    def include(op_a, op_b):
        if op_a.is_insert() and op_b.is_insert(): op_ap = op_a.include_ii(op_b)
        elif op_a.is_insert() and op_b.is_delete(): op_ap = op_a.include_id(op_b)
        elif op_a.is_delete() and op_b.is_insert(): op_ap = op_a.include_di(op_b)
        elif op_a.is_delete() and op_b.is_delete(): op_ap = op_a.include_dd(op_b)
        return op_ap
    
    def include_ii(op_a, op_b):
        assert(op_a.is_insert())
        assert(op_b.is_insert())
        
        if (op_a.p < op_b.p): return copy.deepcopy(op_a)
        else: return InsertOperation(op_a.s, op_a.p + op_b.l)
    
    def include_id(op_a, op_b):
        assert(op_a.is_insert())
        assert(op_b.is_delete())
        
        if (op_a.p <= op_b.p): return copy.deepcopy(op_a)
        elif (op_a.p > (op_b.p + op_b.l)): return InsertOperation(op_a.s,
            op_a.p - op_b.l)
        else:
            op_ap = InsertOperation(op_a.s, op_b.p)
            op_ap.save_li(op_a, op_b)
            return op_ap
    
    def include_di(op_a, op_b):
        if (op_b.p >= (op_a.p + op_a.l)): return copy.deepcopy(op_a)
        elif (op_a.p >= op_b.p): return DeleteOperation(op_a.l, op_a.p +
                op_b.l)
        else:
            op_return = DeleteOperation(op_b.p - op_a.p, op_a.p)
            op_return.set_sub(op_a.l - (op_b.p - op_a.p), op_b.p + op_b.l)
            return op_return
    
    def include_dd(op_a, op_b):
        if (op_b.p >= (op_a.p + op_a.l)): return copy.deepcopy(op_a)
        elif (op_a.p >= (op_b.p + op_b.l)): return DeleteOperation(op_a.l,
                op_a.p - op_b.l)
        else:
            if ((op_b.p <= op_a.p) and ((op_a.p + op_a.l) <= (op_b.p + op_b.l))): 
                op_return = DeleteOperation(0, op_a.p)
            elif ((op_b.p <= op_a.p) and ((op_a.p + op_a.l) > (op_b.p + op_b.l))): 
                op_return = DeleteOperation(op_a.p + op_a.l - (op_b.p + op_b.l), op_b.p)
            elif ((op_b.p > op_a.p) and ((op_b.p + op_b.l) >= (op_a.p + op_a.l))):
                op_return = DeleteOperation(op_b.p - op_a.p, op_a.p)
            else:
                op_return = DeleteOperation(op_a.l - op_b.l, op_a.p)
            op_return.save_li(op_a, op_b)
            return op_return
    
    def exclude(op_a, op_b):
        if op_a.is_insert() and op_b.is_insert(): op_ap = op_a.exclude_ii(op_b)
        elif op_a.is_insert() and op_b.is_delete(): op_ap = op_a.exclude_id(op_b)
        elif op_a.is_delete() and op_b.is_insert(): op_ap = op_a.exclude_di(op_b)
        elif op_a.is_delete() and op_b.is_delete(): op_ap = op_a.exclude_dd(op_b)
        return op_ap
    
    def exclude_ii(op_a, op_b):
        if (op_a.p < op_b.p): return copy.deepcopy(op_a)
        elif (op_a.p > (op_b.p + op_b.l)): return InsertOperation(op_a.s, op_a.p - op_b.l)
        else:
            op_return = InsertOperation(op_a.s, op_a.p - op_b.p)
            op_return.save_ra(op_b)
            return op_return

    def exclude_id(op_a, op_b):
        if (op_a.check_li(op_b)): return op_a.recover()
        elif (op_a.p < op_b.p): return copy.deepcopy(op_a)
        else: return InsertOperation(op_a.s, op_a.p + op_b.l)

    def exclude_di(op_a, op_b):
        if ((op_a.p + op_a.l) < op_b.p): return copy.deepcopy(op_a)
        elif (op_a.p >= (op_b.p + op_b.l)): return DeleteOperation(op_a.l, op_a.p - op_b.l)
        else:  
            if ((op_b.p <= op_a.p) and ((op_a.p + op_a.l) <= (op_b.p + op_b.l))):
                op_return = DeleteOperation(op_a.l, op_a.p - op_b.p)
            elif ((op_b.p <= op_a.p) and ((op_a.p + op_a.l) > (op_b.p + op_b.l))):
                op_return = DeleteOperation(op_b.p+op_b.l - op_a.p, op_a.p - op_b.p)
                op_return.set_sub((op_a.p+op_a.l) - (op_b.p+op_b.l), op_b.p)
            elif ((op_a.p < op_b.p) and ((op_b.p + op_b.l) <= (op_a.p + op_a.l))):
                op_return = DeleteOperation(op_b.l, 0)
                op_return.set_sub(op_a.l - op_b.l, op_a.p)
            else:
                op_return = DeleteOperation(op_a.l+op_a.p - op_b.p, 0)
                op_return.set_sub(op_b.p - op_a.p, op_a.p)
            op_return.save_ra(op_b)
            return op_return
    
    def exclude_dd(op_a, op_b):
        if op_a.check_li(op_b): return op_a.recover_li(op_b)
        elif (op_b.p >= (op_a.p + op_a.l)): return copy.deepcopy(op_a)
        elif (op_a.p >= op_b.p): return DeleteOperation(op_a.l, op_a.p + op_b.l)
        else:
            op_return = DeleteOperation(op_b.p - op_a.p, op_a.p)
            op_return.set_sub(op_a.l - (op_b.p - op_a.p), op_b.p + op_b.l)
            return op_return
        
    def equals(self, op):
        #FIXME: should throw exception
        print "Not implemented"
    
    def save_ra(self, op):
        self._relative = op

    def check_ra(self, op):
        return self._relative == op

    def check_li(self, op):
        return self._backup.has_key(op)

    def __hash__(self):
        #FIXME: do something smart here
        return 0

class DeleteOperation(Operation):
    def __init__(self, length, position):
        assert(type(length) is int)
        assert(type(position) is int)
        self.p = position
        self.l = length
        self._backup = {}
    
    def __str__(self):
        return "Delete[%d,%d]" % (self.p, self.l)
    
    def is_delete(self):
        return True
    
    def __eq__(self, op):
        return self.equals(op)

    def equals(self, op):
        return self.p == op.p and self.l == op.l
    
    def set_sub(self, length, position):
        """Save a sub delete operation."""
        self.sl = length
        self.sp = position
        self._sub = True
    
    def is_split(self):
        return self._sub
    
    def save_li(self, op_a, op_b):
        assert(op_a.is_delete())
        self._backup[op_b] = (op_a.l, op_a.p)
    
    def recover_li(self, op):
        assert(self._backup.has_key(op))
        self.l, self.p = self._backup[op]

class InsertOperation(Operation):
    def __init__(self, text, position):
        assert(type(text) is str)
        assert(type(position) is int)
        self.s = text
        self.p = position
        self.l = len(text)
        self._backup = {}
    
    def __str__(self):
        return "Insert[\"%s\",%d]" % (self.s, self.p)
    
    def is_insert(self):
        return True
    
    def __eq__(self, op):
        return self.equals(op)

    def equals(self, op):
        return self.s == op.s and self.p == op.p and self.l == op.l
    
    def save_li(self, op_a, op_b):
        assert(op_a.is_insert())
        self._backup[op_b] = (op_a.s, op_a.p)

    def recover_li(self, op):
        assert(self._backup.has_key(op))
        self.l, self.p = self._backup[op]
 
