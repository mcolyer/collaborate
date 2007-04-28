import copy
import libxml2
import sys
import gtk
import gobject
import gconf
import gnomekeyring
import gtk.glade
import socket
import re
import select

GCONF_KEY_BASE = '/apps/gedit-2/plugins/collaborate'
GCONF_KEY_JABBER_SERVER = GCONF_KEY_BASE + '/jabber_server'

GLADE_FILE = '/home/mcolyer/.gnome2/gedit/plugins/collaborate.glade'

try:
    import gedit
    
    class CollaboratePlugin(gedit.Plugin):
        def __init__(self):
            self.glade_tree = gtk.glade.XML(GLADE_FILE)
            self.keyring = gnomekeyring.get_default_keyring_sync()
        
        def activate(self, window):
            window.connect("tab-added", self.add)
            CollaborateWindowHelper(self, window)

        def deactivate(self, window):
            pass
        
        def is_configurable(self):
            return true
        
        def create_configure_dialog(self):
            dic = {"on_preferences_response" : self.on_preferences_response,
                   "on_server_unfocus": self.on_server_unfocus}
            self.glade_tree.signal_autoconnect(dic)

            # Set the server field equal to the stored value
            server = gconf.client_get_default().get_string(GCONF_KEY_JABBER_SERVER)
            if server is not None:
                self.glade_tree.get_widget('server').set_text(server)

            self.retrieve_keyring_data(server)
                    
            return self.glade_tree.get_widget('preferences')

        def retrieve_keyring_data(self, server):
            if server != None and server != '':
                try:
                    results = gnomekeyring.find_items_sync(gnomekeyring.ITEM_NETWORK_PASSWORD, {'server': server, 'protocol': 'jabber'})
                except gnomekeyring.DeniedError:
                    user = ""
                    password = ""
                else:
                    #FIXME: This is hack, we are only allowing one account to a specific server
                    user = results[0].attributes['user']
                    password = results[0].secret

            self.glade_tree.get_widget('user').set_text(user)
            self.glade_tree.get_widget('password').set_text(password)

        def set_keyring_data(self, server, user, password):
            #FIXME: Should we remove old keyring entries?

            # Check to make sure whether we need to update the keyring entry or not
            try:
                results = gnomekeyring.find_items_sync(gnomekeyring.ITEM_NETWORK_PASSWORD, {'server': server, 'user': user, 'protocol': 'jabber'})
            except gnomekeyring.DeniedError:
                # The entry doesn't exist
                gnomekeyring.item_create_sync(self.keyring,
                                                  gnomekeyring.ITEM_NETWORK_PASSWORD,
                                                  '',
                                                  {'server': server, 'user': user, 'authtype': 'password', 'protocol': 'jabber'},
                                                  password,
                                                  True)
            else:
                #FIXME: This is hack, we are only allowing one account to a specific server
                # The entry exists, make sure it isn't identical
                if password != results[0].secret:
                    gnomekeyring.item_create_sync(self.keyring,
                                                  gnomekeyring.ITEM_NETWORK_PASSWORD,
                                                  '',
                                                  {'server': server, 'user': user, 'authtype': 'password', 'protocol': 'jabber'},
                                                  password,
                                                  True)

        def on_server_unfocus(self, widget, event, data=None):
            server = self.glade_tree.get_widget('server').get_text()
            orig_server = gconf.client_get_default().get_string(GCONF_KEY_JABBER_SERVER)
            if orig_server != server:
                self.retrieve_keyring_data(server)

        def on_preferences_response(self, dialog, response_id, data=None):
            if response_id == gtk.RESPONSE_OK:
                server = self.glade_tree.get_widget('server').get_text()
                gconf.client_get_default().set_string(GCONF_KEY_JABBER_SERVER, server)

                user = self.glade_tree.get_widget('user').get_text()
                password = self.glade_tree.get_widget('password').get_text()
                
                self.set_keyring_data(server, user, password)

            dialog.hide()

        def update_ui(self, window):
            pass
        
        def add(self, window, tab):
            print "opened"
            d = Document(tab.get_document())
    
    # Menu item example, insert a new item in the Tools menu
    ui_str = """<ui>
      <menubar name="MenuBar">
        <menu name="ToolsMenu" action="Tools">
          <placeholder name="ToolsOps_2">
            <menuitem name="ExamplePy" action="ExamplePy"/>
          </placeholder>
        </menu>
      </menubar>
    </ui>
    """
    class CollaborateWindowHelper:
        def __init__(self, plugin, window):
            self._window = window
            self._plugin = plugin

            # Insert menu items
            self._insert_menu()

        def deactivate(self):
            # Remove any installed menu items
            self._remove_menu()

            self._window = None
            self._plugin = None
            self._action_group = None

        def _insert_menu(self):
            # Get the GtkUIManager
            manager = self._window.get_ui_manager()

            # Create a new action group
            self._action_group = gtk.ActionGroup("CollaboratePluginActions")
            self._action_group.add_actions([("ExamplePy", None, "Share document",
                                             None, "Share the document",
                                             self.on_share_document_activate)])

            # Insert the action group
            manager.insert_action_group(self._action_group, -1)

            # Merge the UI
            self._ui_id = manager.add_ui_from_string(ui_str)

        def _remove_menu(self):
            # Get the GtkUIManager
            manager = self._window.get_ui_manager()

            # Remove the ui
            manager.remove_ui(self._ui_id)

            # Remove the action group
            manager.remove_action_group(self._action_group)

            # Make sure the manager updates
            manager.ensure_update()

        def update_ui(self):
            self._action_group.set_sensitive(self._window.get_active_document() != None)

        # Menu activate handlers
        def on_share_document_activate(self, action):
            doc = self._window.get_active_document()
            if not doc:
                return

    class Document:
        socket = None
        _geditDocument = None

        def __init__(self, doc):
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect("/tmp/gedit-jabber")
            gobject.idle_add(self.handle_socket)
           
            self.socket.sendall("<connect/>\n")
            self.socket.sendall("<open-channel/>\n")
            self._geditDocument = doc
            self._geditDocument.connect("insert-text", self.insert)
            self._geditDocument.connect("delete-range", self.delete)
        
        def handle_socket(self):
            in_list, out_list, err_list = select.select([self.socket], [], [], 0.01)
            if len(in_list) > 0:
                for connection in in_list:
                    data = connection.recv(2048)
                    self.execute(Operation.parse(data))

            return True
 
        def deactivate(self):
            self.socket.close()

        def execute(self, command):
            if isinstance(command, InsertOperation):
                self._geditDocument.insert(self._geditDocument.get_iter_at_offset(command.p), command.s)
            elif isinstance(command, DeleteOperation):
                self._geditDocument.delete(self._geditDocument.get_iter_at_offset(command.p), self._geditDocument.get_iter_at_offset(command.p+command.l))

        def insert(self, textbuffer, iter, text, length, data=None):
            self.socket.sendall(str(InsertOperation(text, iter.get_offset()))+"\n")
        
        def delete(self, textview, start, end, data=None):
            offset = start.get_offset()
            length = end.get_offset() - offset
            self.socket.sendall(str(DeleteOperation(length, offset)))
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
 
