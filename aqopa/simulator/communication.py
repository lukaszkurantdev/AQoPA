'''
Created on 07-05-2013

@author: Damian Rusinek <damian.rusinek@gmail.com>
'''
from aqopa.model import original_name, name_indexes,\
    CommunicationInstruction
from aqopa.simulator.error import RuntimeException

class ChannelMessage():
    """
    Message sent through channel.
    """
    
    def __init__(self, sender, expression):
        self.sender = sender
        self.expression = expression
        
        
class ChannelMessageRequest():
    """
    Representation of hosts' requests for messages.
    """
    
    def __init__(self, receiver, communication_instruction):
        """ """
        self.receiver       = receiver
        self.instruction    = communication_instruction

class Channel():
    """
    Simulation channel.
    """
    
    def __init__(self, name, buffer_size):
        self.name = name
        self._buffer_size           = buffer_size   # Size of buffer, negative means that buffer is unlimited,
                                                    # zero means that channel is asynhronous 
        
        self._connected_hosts = [] # List of hosts that can use this channel
        self._connected_processes = [] # List of processes that can use this channel
        self._host_indexes = {} # Map of host -> index of the message that should be checked in the next step for this host
                                # If all indexes are greater than N, we can remove N first messages 
        
        self._waiting_requests      = []
        self._sent_messages         = []
        self._dropped_messages_cnt  = 0
        
    def connect_with_host(self, host):
        """
        Connect channel with host if it is not already connected.
        """
        if host in self._connected_hosts:
            return
        self._connected_hosts.append(host)
        
    def connected_with_host(self, host):
        """
        Returns True if host is connected with this channel.
        """
        return host in self._connected_hosts
        
    def connect_with_process(self, process):
        """
        Connect channel with process if it is not already connected.
        """
        if process in self._connected_processes:
            return
        self._connected_processes.append(process)
        
    def connected_with_process(self, process):
        """
        Returns True if process is connected with this channel.
        """
        return process in self._connected_processes
    
    def is_synchronous(self):
        """
        Returns True if channel is synchronous.
        """
        return self._buffer_size == 0
    
    def has_unlimited_buffer(self):
        """
        Returns True if channel has unlimited buffer.
        """
        return self._buffer_size < 0
    
    def get_number_of_dropped_messages(self):
        """
        Return number of messages dropped on this channel  
        """
        return self._dropped_messages_cnt
        
    def get_queue_of_receiving_hosts(self, number):
        """
        Returns list of hosts waiting for message on this channel.
        List is limited by number parameter.
        If there is less than number hosts waiting, Nones are returned 
        if channel can store messages in buffer.
        """
        hosts = []
        
        if self.is_synchronous():
            accepted_expressions_count = min([self._needed_expressions_count(), number])
            expected_messages_count = 0
            
            i = 0
            while expected_messages_count <= accepted_expressions_count and i < len(self._waiting_requests):
                request = self._waiting_requests[i]
                
                expected_messages_count += len(request.instruction.variables_names)
                
                if expected_messages_count <= accepted_expressions_count:
                    for j in range(0, len(request.instruction.variables_names)):
                        hosts.append(request.receiver)
                
                i += 1
                
        else:
            needed_messages_count = self._needed_expressions_count()
            accepted_expressions_count = number
            if not self.has_unlimited_buffer():
                accepted_expressions_count = min([self._buffer_size-len(self._sent_messages)+needed_messages_count, 
                                                  number])
    
            expected_messages_count = 0
            i = 0
            while expected_messages_count <= accepted_expressions_count:
                
                if i >= len(self._waiting_requests):
                    for j in range(expected_messages_count, accepted_expressions_count):
                        hosts.append(None)
                    break
                    
                request = self._waiting_requests[i]
                expected_messages_count += len(request.instruction.variables_names)
                if expected_messages_count <= accepted_expressions_count:
                    for j in range(0, len(request.instruction.variables_names)):
                        hosts.append(request.receiver)
                
                i += 1
                
        return hosts
    
    def get_queue_of_sending_hosts(self, number):
        """
        Return list of hosts who had sent messages to channel before.
        Works only for asynchronous channels. For synchronous channels always is returned empty array.
        Returns at most number hosts.
        """
        hosts = []
        if not self.is_synchronous():
            accepted_expressions_count = min([len(self._sent_messages), number])
            for i in range(0, accepted_expressions_count):
                message = self._sent_messages[i]
                hosts.append(message.sender)
            
        return hosts
    
    def waiting_for_message(self, request):
        """
        Returns True if channel is waiting for message.
        """
        for i in range(0, len(self._waiting_requests)):
            waiting_request = self._waiting_requests[i]
            if waiting_request.instruction == request.instruction and waiting_request.receiver == request.receiver:
                return True
        return False
    
    def wait_for_message(self, request):
        """
        Add host to the queue of hosts waiting for messages.
        Host can wait for many expressions.
        """
        if not self.connected_with_host(request.receiver):
            raise RuntimeException("Channel '%s' is not connected with host '%s'." % (self.name, request.receiver.name))
        
        if not self.waiting_for_message(request):
            self._waiting_requests.append(request)
            
        # Check if request can be bound with expressions
        self._bind_sent_expressions_with_receivers()
    
    def get_number_of_waiting_expressions(self):
        """
        Count expressions that are needed to fulfil all waiting requests.
        """
        cnt = 0
        for request in self._waiting_requests:
            cnt += len(request.instruction.variables_names)
        return cnt
    
    def send_message(self, sender_host, expressions):
        """
        Accept message with expressions.
        """
        if not self.connected_with_host(sender_host):
            raise RuntimeException("Channel '%s' is not connected with host '%s'." % (self.name, sender_host.name))
            
        for e in expressions:
            self._sent_messages.append(ChannelMessage(sender_host, e))
        
        # Check if request can be bound with expressions
        self._bind_sent_expressions_with_receivers()
        
    def _bind_sent_expressions_with_receivers(self):
        """
        Checks if have any messages and requests and if yes, bind them.
        """
        while len(self._waiting_requests) > 0:
            request = self._waiting_requests[0]
            if len(request.instruction.variables_names) > len(self._sent_messages):
                break
            
            size = len(request.instruction.variables_names)
            for i in range(0, size):
                message = self._sent_messages.pop(0)
                
                request.receiver.set_variable(request.instruction.variables_names[i],
                                              message.expression)
                
            request.receiver.get_instructions_context_of_instruction(request.instruction)\
                .goto_next_instruction()
            request.receiver.mark_changed()
            
            self._waiting_requests.pop(0)
            
        if self.is_synchronous():
            self._sent_messages = []
            
    
class Manager():
    """ Channels manager class """
    
    def __init__(self, channels):
        self.channels = channels
        
    def find_channel(self, name, predicate=None):
        """
        """
        for ch in self.channels:
            if ch.name == name:
                if predicate is not None and not predicate(ch):
                    continue
                return ch
        return None
        
    def find_channel_for_current_instruction(self, context):
        """
        Finds channel connected with process/host from current instruction
        and with the channel name from instruction. 
        """
        instruction = context.get_current_instruction()
        if not isinstance(instruction, CommunicationInstruction):
            return None
        return self.find_channel_for_host_instruction(context, context.get_current_host(), 
                                                      instruction)
        
    def find_channel_for_host_instruction(self, context, host, instruction):
        """
        Finds channel connected with process/host from current instruction 
        of passed host and with the channel name from instruction. 
        """
        process = host.get_current_instructions_context().get_process_of_current_list()
        if process:
            return self.find_channel(instruction.channel_name,
                                     predicate=lambda x: x.connected_with_process(process))
        else:
            return self.find_channel(instruction.channel_name,
                                     predicate=lambda x: x.connected_with_host(host))
    
    def build_message_request(self, receiver, communication_instruction):
        """
        Creates a request for message when host executes instruction IN
        """
        return ChannelMessageRequest(receiver, communication_instruction)
    
    