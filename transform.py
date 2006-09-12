#Issues to be dealt with
# Undo/Redo control scheme?
# Unique command identifier
# Timestamping
# Double output commands


################################################
# Inclusion functions
################################################

# General inclusion transformation
def inclusion_transformation(operation_a, operation_b):	
	o_a_type = operation.tagName
	o_b_type = operation.tagName
	
	if check_relative_address(operation_a):
		if check_base_operation(operation_a, operation_b):
			convert_to_absolute_address(operation_a, operation_b)
		else:
			pass
	elif (o_a_type == "insert" and o_b_type == "insert"):
		it_ii(operation_a, operation_b)
	elif (o_a_type == "insert" and o_b_type == "delete"):
		it_id(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "insert"):
		it_di(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "delete"):
		it_dd(operation_a, operation_b)
	
# Inclusion of insert against insert	
def it_ii(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_b_len = len(int(operation_b.getAttribute("string")))
	
	# If it is to the left of the second operation do nothing
	if (o_a_pos < o_b_pos):
		pass
	# If it is to the right of the second operation shift it the proper amount
	else:
		operation_a.setAttribute("position", str(o_a_pos+o_b_len))
	
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
				
# Inclusion of delete against insert
def it_di(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	o_a_len = int(operation_a.getAttribute("length"))
	o_b_len = len(int(operation_a.getAttribute("string")))
	
	# If delete is before the insert operation do nothing
	if (o_b_pos >= (o_a_pos + o_a_len)):
		pass
	# If delete is after the insert operation shift it the proper amount
	elif (o_a_pos >= o_b_pos):
		operation_a.setAttribute("position", str(o_a_pos+o_b_len))	
	# Otherwise the delete is split across the insert and two delete commands are required
	else:
		pass
		#FIXME GENERATE TWO COMMANDS
		
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

################################################
# Exclusion functions
################################################

# General exclusion transformation
def exclusion_transformation(operation_a, operation_b):	
	o_a_type = operation.tagName
	o_b_type = operation.tagName
	
	if check_relative_address(operation_a):
		pass
	elif (o_a_type == "insert" and o_b_type == "insert"):
		et_ii(operation_a, operation_b)
	elif (o_a_type == "insert" and o_b_type == "delete"):
		et_id(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "insert"):
		et_di(operation_a, operation_b)
	elif (o_a_type == "delete" and o_b_type == "delete"):
		et_dd(operation_a, operation_b)	
	
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
			#FIXME two commands
			pass	
		else:
			#FIXME two commands
			pass 
		save_relative_address(operation_a, operation_b)
		
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
		#FIXME TWO COMMANDS

################################################
# Utility functions
################################################
def check_relative_addressing(operation):
	if (operation.getAttribute("relative") == "True"):
		return True
	else:
		return False

def save_relative_address(operation_a, operation_b):
	operation_a.setAttribute("relative", "True")

def check_base_operation(operation_a, operation_b):
	pass

def convert_to_absolute_addressing(operation_a, operation_b):
	o_a_pos = int(operation_a.getAttribute("position"))
	o_b_pos = int(operation_b.getAttribute("position"))
	
	operation_a.setAttribute("position", str(o_a_pos+o_b_pos))
	
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
