import copy
import libxml2
import sys
import gtk
import gobject
import socket
import re
import select

try:
    import gedit
    
    class CollaboratePlugin(gedit.Plugin):
        def activate(self, window):
            window.connect("tab-added", self.add)
        
        def deactivate(self, window):
            pass
        
        def update_ui(self, window):
            pass
        
        def add(self, window, tab):
            print "opened"
            d = Document(tab.get_document())
    
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
 
