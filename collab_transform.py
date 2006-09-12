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
# This file contains all the routines concerning transformation of commands
#

# FIXME: This is not infite in theory.
last_relative_id = 0

################################################
# Inclusion functions
################################################

def list_inclusion_transformation(list_of_operations_a, list_of_operations_b):
	if (len(list_of_operations_a) > 1):
		transformed_command_1 = list_inclusion_transformation([list_of_operations_a[0]], list_of_operations_b)
		transformed_command_2 = list_inclusion_transformation([list_of_operations_a[1]], list_of_operations_b)
		return [transformed_command_1, transformed_command_2]
	
	if (len(list_of_operations_b) == 0):
		return list_of_operations_a[0]
	else:
		if (len(list_of_operations_b) > 1):
			return list_inclusion_transformation(inclusion_transformation(list_of_operations_a[0], list_of_operations_b[0]), list_of_operations_b[1:])
		else:
			return list_inclusion_transformation(inclusion_transformation(list_of_operations_a[0], list_of_operations_b[0]), [])

# General inclusion transformation
def inclusion_transformation(operation_a, operation_b):	
	o_a_type = operation_a.tagName
	o_b_type = operation_b.tagName
	
	if check_relative_address(operation_a):
		if check_base_operation(operation_a, operation_b):
			executable_operations = convert_to_absolute_address(operation_a, operation_b)
		else:
			executable_operations = [operation_a]
	elif (o_a_type == "insert" and o_b_type == "insert"):
		executable_operations = it_ii(operation_a, operation_b)
	elif (o_a_type == "insert" and o_b_type == "delete"):
		executable_operations = it_id(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "insert"):
		executable_operations = it_di(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "delete"):
		executable_operations = it_dd(operation_a, operation_b)
	
	print "INCLUSION: "+executable_operations[0].toxml()+"\n\t"+operation_b.toxml()	
	return executable_operations
	
# Inclusion of insert against insert	
def it_ii(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_b_len = len(operation_b.getAttribute("string"))
	
	# If it is to the left of the second operation do nothing
	if (o_a_pos < o_b_pos):
		pass
	# If it is to the right of the second operation shift it the proper amount
	else:
		operation_a.setAttribute("position", str(o_a_pos+o_b_len))
		
	return [operation_a]
	
# Inclusion of insert against delete
def it_id(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_b_len = len(int(operation_b.getAttribute("string")))
	
	# If it is to the left of the delete operation do nothing
	if (o_a_pos <= on_b_pos):
		pass
	# If it is to the right of the delete operation shift it the proper amount
	elif (o_a_pos >= o_b_pos):
		operation_a.setAttribute("position", str(o_a_pos-o_b_len))
	# If it is within the middle of the delete operation shift it to the beginning
	# of the delete operation, this is arbitrary.
	else:
		save_lost_information(operation_a, operation_b)
		operation_a.setAttribute("position", str(o_b_pos))
		
	return [operation_a]
				
# Inclusion of delete against insert
def it_di(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_a_len = int(operation_a.getAttribute("length"))
	o_b_len = len(operation_a.getAttribute("string"))
	
	# If delete is before the insert operation do nothing
	if (o_b_pos >= (o_a_pos + o_a_len)):
		pass
	# If delete is after the insert operation shift it the proper amount
	elif (o_a_pos >= o_b_pos):
		operation_a.setAttribute("position", str(o_a_pos+o_b_len))	
	# Otherwise the delete is split across the insert and two delete commands are required
	else:		
		operation_a.setAttribute("length", str(o_b_pos-o_a_pos))			
		operation_c = operation_a.cloneNode(False)
		operation_c.setAttribute("length", str(o_a_len-(o_b_pos-o_a_pos)))
		operation_c.setAttribute("position",  str(o_b_pos+o_b_len))
		
		if (removed_string == operation_a.getAttribute("removed-string")):
			operation_a.setAttribute("removed-string", removed_string[0:o_b_pos-o_a_pos])
			operation_c.setAttribute("removed-string", removed_string[o_b_pos-o_a_pos:])
		
		return [operation_a, operation_c]
	
	return [operation_a]
		
# Inclusion of delete against delete
def it_dd(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_a_len = int(operation_a.getAttribute("length"))
	o_b_len = int(operation_b.getAttribute("length"))

	# If the delete is to the left of the command it is against
	if (o_b_pos >= (o_a_pos + o_a_len)):
		pass
	# If the delete is to the right of the command it is against
	elif (o_a_pos >= (o_b_pos + o_b_len)):
		operation_a.setAttribute("position", str(o_a_pos-o_b_len))
	# If the delete is in the middle
	else:
		# Completely Contained
		if (o_b_pos <= o_a_pos and ((o_a_pos + o_a_len) <= (o_b_pos + o_b_len))):
			operation_a.setAttribute("length", "0")
		
		# If it overlaps to the right
		elif (o_b_pos <= o_a_pos and ((o_a_pos + o_a_len) > (o_b_pos + o_b_len))):
			operation_a.setAttribute("length", str(o_a_pos+o_a_len-(o_b_pos+o_b_len)))
			
		# If it overlaps to the left
		elif (o_b_pos > o_a_pos and ((o_b_pos + o_b_len) >= (o_a_pos + o_a_len))):
			operation_a.setAttribute("length", str(o_b_pos-o_a_pos))
		# If both start at same position and op_a is longer than op_b
		# resize it.
		else:
			operation_a.setAttribute("length", str(o_b_len-o_a_len))
		
		#FIXME: Need to identify which command it lost information 
		save_lost_information(operation_a)
	
	return [operation_a]

################################################
# Exclusion functions
################################################
def list_exclusion_transformation(list_of_operations_a, list_of_operations_b):
	if (len(list_of_operations_a) > 1):
		transformed_command_1 = list_exclusion_transformation([list_of_operations_a[0]], list_of_operations_b)
		transformed_command_2 = list_exclusion_transformation([list_of_operations_a[1]], list_of_operations_b)
		return [transformed_command_1, transformed_command_2]
	
	if (len(list_of_operations_b) == 0):
		return list_of_operations_a[0]
	else:
		if (len(list_of_operations_b) > 1):
			return list_exclusion_transformation(exclusion_transformation(list_of_operations_a[0], list_of_operations_b[0]), list_of_operations_b[1:])
		else:
			return list_exclusion_transformation(exclusion_transformation(list_of_operations_a[0], list_of_operations_b[0]), [])

# General exclusion transformation
def exclusion_transformation(operation_a, operation_b):	
	o_a_type = operation.tagName
	o_b_type = operation.tagName
	print "EXCLUSION: "+o_a_type+" "+o_b_type
	if check_relative_address(operation_a):
		executable_operations = [operation_a]
	elif (o_a_type == "insert" and o_b_type == "insert"):
		executable_operations = et_ii(operation_a, operation_b)
	elif (o_a_type == "insert" and o_b_type == "delete"):
		executable_operations = et_id(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "insert"):
		executable_operations = et_di(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "delete"):
		executable_operations = et_dd(operation_a, operation_b)	
	
	return executable_operations
	
# Exclusion of insert against insert	
def et_ii(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_b_len = len(int(operation_b.getAttribute("string")))

	# If the string to transform is to the left of the one against
	if (o_a_pos <= o_b_pos):
		pass
	# If the string is to the right of the it is against
	elif (o_a_pos >= (o_b_pos + o_b_len)):
		operation_a.setAttribute("position", str(o_a_pos - o_b_len))
	# Otherwise it is in the middle
	else :
		operation_a.setAttribute("position", str(o_a_pos - o_b_pos))
		save_relative_address(operation_a, operation_b)
	
	return [operation_a]
		
# Exclusion of insert against delete
def et_id(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_b_len = len(int(operation_b.getAttribute("string")))
	
	if check_lost_information(operation_a):
		recover_lost_information(operation_a, operation_b)
	
	# If the operation is to the left	
	elif (o_a_pos <= o_b_pos):
		pass
	# Otherwise put it past the delete command
	else:
		operation_a.setAttribute("position", str(o_a_pos + o_b_len))
	
	return [operation_a]
	
# Exclusion of delete against insert
def et_di(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_a_len = len(int(operation_a.getAttribute("string")))
	o_b_len = len(int(operation_b.getAttribute("string")))
	
	if ((o_a_pos + o_a_len) <= o_b_pos):
		pass
	elif (o_a_pos >= (o_b_pos+o_b_len)):
		operation_a.setAttribute("position", str(o_a_pos - o_b_len))
	else:
		if (o_b_pos <= o_a_pos and  (o_a_pos + o_a_len) <= (o_b_pos + o_b_len)):
			operation_a.setAttribute("position", str(o_a_pos - o_b_pos))
		elif (o_b_pos <= o_a_pos and (o_a_pos + o_a_len) > (o_b_pos + o_b_len)):
			operation_a.setAttribute("length", str(o_b_pos+o_b_len-o_a_pos))
			operation_a.setAttribute("position", str(o_a_pos-o_b_pos))
			operation_c = operation_a.cloneNode(False)
			operation_c.setAttribute("length", str((o_a_pos+o_a_len)-(o_b_pos+o_b_len)))
			operation_c.setAttribute("position",  str(o_b_pos))
			
			if (removed_string == operation_a.getAttribute("removed-string")):
				operation_a.setAttribute("removed-string", removed_string[0:o_b_pos+o_b_len-o_a_pos])
				operation_c.setAttribute("removed-string", removed_string[o_b_pos+o_b_len-o_a_pos:])

			save_relative_address(operation_a, operation_b)
			return [operation_a, operation_c]
		elif (o_a_pos < o_b_pos and (o_b_pos + o_b_len) <= (o_a_pos+o_a_len)): 
			operation_a.setAttribute("length", str(o_b_len))
			operation_a.setAttribute("position", str(0))
			operation_c = operation_a.cloneNode(False)
			operation_c.setAttribute("length", str(o_a_len-o_b_len))
			operation_c.setAttribute("position",  str(o_a_pos))
			
			if (removed_string == operation_a.getAttribute("removed-string")):
				operation_a.setAttribute("removed-string", removed_string[0:o_b_len])
				operation_c.setAttribute("removed-string", removed_string[o_b_len:])
			
			save_relative_address(operation_a, operation_b)
			return [operation_a, operation_c]			
		else:
			operation_a.setAttribute("length", str(o_a_pos+o_a_len-o_b_pos))
			operation_a.setAttribute("position", str(0))
			operation_c = operation_a.cloneNode(False)
			operation_c.setAttribute("length", str(o_b_pos-o_a_pos))
			operation_c.setAttribute("position",  str(o_a_pos))
			
			if (removed_string == operation_a.getAttribute("removed-string")):
				operation_a.setAttribute("removed-string", removed_string[0:o_b_pos+o_b_len-o_a_pos])
				operation_c.setAttribute("removed-string", removed_string[o_b_pos+o_b_len-o_a_pos:])
			
			save_relative_address(operation_a, operation_b)
			return [operation_a, operation_c]			
		
		save_relative_address(operation_a, operation_b)
	return [operation_a]
		
# Exclusion of delete against delete
def et_dd(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_a_len = len(int(operation_b.getAttribute("string")))
	o_b_len = len(int(operation_b.getAttribute("string")))
	
	if (check_lost_information(operation_a)):
		recover_lost_information(operation_a)
	elif (o_b_pos >= (o_a_pos + o_a_len)):
		pass
	elif (o_a_pos >= o_b_pos):
		operation_a.setAttribute("position", str(o_a_pos + o_b_len))
	else:
		operation_a.setAttribute("length", str(o_b_pos-o_a_pos))			
		operation_c = operation_a.cloneNode(False)
		operation_c.setAttribute("length", str(o_a_len-(o_b_pos-o_a_pos)))
		operation_c.setAttribute("position",  str(o_b_pos+o_b_len))
		
		if (removed_string == operation_a.getAttribute("removed-string")):
			operation_a.setAttribute("removed-string", removed_string[0:o_b_pos-o_a_pos])
			operation_c.setAttribute("removed-string", removed_string[o_b_pos-o_a_pos:])
		
		return [operation_a, operation_c]
	return [operation_a]

################################################
# Utility functions
################################################
def check_relative_address(operation):
	if (operation.getAttribute("relative") == "True"):
		return True
	else:
		return False

def save_relative_address(operation_a, operation_b):
	operation_a.setAttribute("relative", "True")
	operation_a.setAttribute("relative_id", last_relative_id)
	operation_b.setAttribute("relative_id", last_relative_id)
	relative_id += 1
	
def check_base_operation(operation_a, operation_b):
	if (operation_a.getAttribute("relative_id") == operation_b.getAttribute("relative_id")):
		return True
	else:
		return False

def convert_to_absolute_addressing(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	
	operation_a.setAttribute("position", str(o_a_pos+o_b_pos))
	
	operation_a.removeAttribute("relative_id")
	operation_b.removeAttribute("relative_id")
	
	return [operation_a]
	
def save_lost_information(operation):
	operation.setAttribute("position-bkup", operation.getAttribute("position"))
	
	if (operation.tagName == "delete"):
		operation.setAttribute("length-bkup", operation.getAttribute("length"))
		
def restore_information(operation):
	operation.setAttribute("position", operation.getAttribute("position-bkup"))
	operation.removeAttribute("position-bkup")
	
	if (operation.tagName == "delete"):
		operation.setAttribute("length", operation.getAttribute("length-bkup"))
		operation.removeAttribute("length-bkup")
