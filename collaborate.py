"""
Author: Matthew Colyer <matt@colyer.name>

Inspiration/copying came from the GNOME live pages about the gedit plugins.

"""

import copy
import sys
import gtk
import gobject
import gconf
import re
import os.path
import time
import xml.dom.minidom
import xml.dom.ext
import md5
import dbus
import telepathy

# Connect dbus to the glib mainloop
from dbus.mainloop.glib import DBusGMainLoop
DBusGMainLoop(set_as_default=True)

GCONF_KEY_BASE = '/apps/gedit-2/plugins/collaborate'
MISSION_CONTROL_BUS = 'org.freedesktop.Telepathy.Houston.MissionControl'
MISSION_CONTROL_BUS_PATH = '/org/freedesktop/Telepathy/Houston/MissionControl'

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
            return false
        
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
            self._action_group.add_actions([('Share', None, 'Share document',
                                             None, 'Share the current document',
                                             self.on_share_document_activate)])
            self._action_group.add_actions([('Join', None, 'Join a document',
                                             None, 'Join a shared document',
                                             self.on_join_document_activate)])


            manager.insert_action_group(self._action_group, -1)
            
            # Merge the UI
            ui_str = """<ui>
                  <menubar name="MenuBar">
                    <menu name="ToolsMenu" action="Tools">
                      <placeholder name="ToolsOps_2">
                        <menuitem name="CollaborateShare" action="Share"/>
                        <menuitem name="CollaborateJoin" action="Join"/>
                        <separator/>
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
            view = self._window.get_active_view()
            if not doc:
                return
            self._documents.append(Document(self._plugin, doc, view))

        def on_join_document_activate(self, action):
            dialog = gtk.Dialog(title='Document Address', 
                                parent=self._window,
                                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK, gtk.RESPONSE_ACCEPT),
                                flags=gtk.DIALOG_MODAL,
                                )
            entry = gtk.Entry()
            dialog.vbox.pack_start(entry, padding=6)
            dialog.connect('response', self.document_address_response, entry)
            dialog.show_all()

        def document_address_response(self, dialog, response_id, data=None):
            #FIXME: Validate address input
            document_address = data.get_text()
            dialog.destroy()

            if response_id == gtk.RESPONSE_REJECT:
                return

            self._window.create_tab(True)
            doc = self._window.get_active_document()
            view = self._window.get_active_view()
            if not doc:
                return
            self._documents.append(Document(self._plugin, doc, view, document_address))
            

    class Document:
        _gedit_document = None

        def __init__(self, plugin, doc, view, remote_channel_address=None):
            self._plugin = plugin
            self._participants = {}

            # Ask Houston if there are any jabber accounts available.
            bus = dbus.SessionBus()
            mission_control = bus.get_object(MISSION_CONTROL_BUS, MISSION_CONTROL_BUS_PATH)
            connected_accounts  = mission_control.GetConnectedAccounts()
            jabber_connected_accounts = filter(lambda x: x[3] == 'Jabber', connected_accounts)
            
            if len(jabber_connected_accounts) == 0:
                # TODO: If none then alert the user to add an account.
                window = gtk.MessageDialog(parent=None,
                                           type=gtk.MESSAGE_INFO,
                                           buttons=gtk.BUTTONS_CLOSE,
                                           flags=gtk.DIALOG_MODAL,
                                           message_format="You must have a connected jabber account before you are able to share a document. Please make sure that an account is available and connected.")
                window.connect('response', self.account_message_response)
                window.show()

            elif len(jabber_connected_accounts) == 1:
                # If 1 then use it
                proxy_object = bus.get_object(jabber_connected_accounts[0][0], jabber_connected_accounts[0][1])
                connection = dbus.Interface(proxy_object, telepathy.interfaces.CONN_INTERFACE)
                handle = connection.RequestHandles(telepathy.CONNECTION_HANDLE_TYPE_ROOM, [remote_channel_address])[0]
                transport_path = connection.RequestChannel(telepathy.interfaces.CHANNEL_TYPE_TEXT, telepathy.CONNECTION_HANDLE_TYPE_ROOM, handle, True)
                proxy_object = bus.get_object(jabber_connected_accounts[0][0], transport_path)
                self._transport = dbus.Interface(proxy_object, telepathy.interfaces.CHANNEL_TYPE_TEXT)
            else:
                # TODO: If >1 then allow them to choose one
                pass

            # Connect up the recieved messages to be parsed.
            self._transport.connect_to_signal("Received", self.handle_message)

            self._gedit_document = doc
            self._gedit_view = view
            self._insert_signal_id = self._gedit_document.connect('insert-text', self.insert)
            self._delete_signal_id = self._gedit_document.connect('delete-range', self.delete)
        
        def account_message_response(self, dialog, response_id, data=None):
            dialog.destroy()
            bus = dbus.SessionBus()
            mission_control = bus.get_object(MISSION_CONTROL_BUS, MISSION_CONTROL_BUS_PATH)
            mission_control.ShowAccounts()

        def deactivate(self):
            pass

        def handle_message(self, id, timestamp, sender, type, flags, text):
            try:
                # Attempt to parse the message
                operation = Operation.parse(str(text))

                # Lock the document from editing and remove callbacks
                self._gedit_view.set_property('editable', False)
                self._gedit_document.disconnect(self._insert_signal_id)
                self._gedit_document.disconnect(self._delete_signal_id)

                # Perform the operation
                self.execute(operation, sender)

                # Add the callbacks and allow editing again
                self._insert_signal_id = self._gedit_document.connect('insert-text', self.insert)
                self._delete_signal_id = self._gedit_document.connect('delete-range', self.delete)
                self._gedit_view.set_property('editable', True)

            except InvalidOperation:
                # Ignore invalid messages for now
                pass

        def execute(self, command, participant):
            # FIXME: Should really use the tag table instead of my own hash table
            if not self._participants.has_key(participant):
                self._participants[participant] = self._gedit_document.create_tag()
                
                #FIXME: Get more creative here, limited to only 6 colors
                self._participants[participant].set_property('background', 
                        ['#FFF595', '#ADC7E3', '#C9F3A0', '#FFD394', '#D4BCD2','#F89999'][len(self._participants) % 7])

            if isinstance(command, InsertOperation):
                self._gedit_document.insert_with_tags(self._gedit_document.get_iter_at_offset(command.p), command.s, self._participants[participant])
            elif isinstance(command, DeleteOperation):
                self._gedit_document.delete(self._gedit_document.get_iter_at_offset(command.p), self._gedit_document.get_iter_at_offset(command.p+command.l))

        def insert(self, textbuffer, iter, text, length, data=None):
            self._transport.Send(telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL, str(InsertOperation(text, iter.get_offset()))+"\n")
        
        def delete(self, textview, start, end, data=None):
            offset = start.get_offset()
            length = end.get_offset() - offset
            self._transport.Send(telepathy.CHANNEL_TEXT_MESSAGE_TYPE_NORMAL, str(DeleteOperation(length, offset)))

        def hash(self):
            return md5.new(this._gedit_document.get_uri()).digest()
    
except:
    print "WARNING: No Gedit environment"

class InvalidOperation(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

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
        else:
            raise InvalidOperation, "Invalid message string"

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
 
