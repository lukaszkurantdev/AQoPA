'''
Created on 22-04-2013

@author: Damian Rusinek <damian.rusinek@gmail.com>
'''

from qopml.interpreter.model.parser.lex_yacc.parser import LexYaccParserExtension
from qopml.interpreter.model import Function
import sys


class Builder():
    """
    Builder for creating function objects
    """
    
    def build_function(self, token):
        """
            FUN IDENTIFIER function_params SEMICOLON 
            FUN IDENTIFIER function_params function_comment SEMICOLON
            FUN IDENTIFIER function_params function_qopml_params SEMICOLON
            FUN IDENTIFIER function_params function_qopml_params function_comment SEMICOLON
        """
        f = Function(token[2], params=token[3])
        
        if len(token) == 6:
            if isinstance(token[4], list):
                f.qop_params = token[4]
            elif isinstance(token[4], str):
                f.comment = token[4]
                
        if len(token) == 7:
            f.qop_params = token[4]
            f.comment = token[5]
        
        return f


class ParserExtension(LexYaccParserExtension):
    """
    Extension for parsing functions
    """
    
    def __init__(self):
        LexYaccParserExtension.__init__(self)
        
        self.open_blocks_cnt = 0
        self.fun_left_brackets_cnt = 0
        
        self.builder = Builder()

    ##########################################
    #           RESERVED WORDS
    ##########################################
    
    def word_functions_specification(self, t):
        t.lexer.push_state('functions')
        return t
    
    def word_fun(self, t):
        self.fun_left_brackets_cnt = 0
        return t
    
    ##########################################
    #                TOKENS
    ##########################################
    
    def token_block_open(self, t):
        r'{'
        self.open_blocks_cnt += 1
        return t
    
    def token_block_close(self, t):
        r'}'
        self.open_blocks_cnt -= 1
        if self.open_blocks_cnt == 0:
            t.lexer.pop_state()
        return t
    
    def token_lparan(self, t):
        r'\('
        self.fun_left_brackets_cnt += 1
        if self.fun_left_brackets_cnt == 2:
            t.lexer.push_state('functioncomment')
        return t

    # Function Comment State
    def token_funcomment_error(self, t):
        sys.stderr.write("Line [%s:%s]: Illegal character '%s' \n" % (t.lexer.lineno, t.lexer.lexpos, t.value[0]))
    
    
    def token_funcomment_rparan(self, t):
        r'\)'
        t.lexer.pop_state()
        return t
    
    ##########################################
    #                RULES
    ##########################################
    
    def functions_specification(self, t):
        """
        specification : FUNCTIONS_SPECIFICATION BLOCK_OPEN functions_list BLOCK_CLOSE
        """
        pass
    
    
    def functions_list(self, t):
        """
        functions_list : function 
                    | functions_list function
        """
        pass
    
    def function(self, t):
        """
        function : FUN IDENTIFIER function_params SEMICOLON 
            | FUN IDENTIFIER function_params function_comment SEMICOLON
            | FUN IDENTIFIER function_params function_qopml_params SEMICOLON
            | FUN IDENTIFIER function_params function_qopml_params function_comment SEMICOLON
        """
        self.parser.store.functions.append(self.builder.build_function(t))
    
    def function_comment(self, t):
        """
        function_comment : LPARAN COMMENT RPARAN
        """
        t[0] = t[2]
    
    def function_params(self, t):
        """
        function_params : LPARAN RPARAN
                    | LPARAN identifiers_list RPARAN
        """
        if len(t) > 3:
            t[0] = t[2]
        else:
            t[0] = []

    
    def function_qopml_params(self, t):
        """
        function_qopml_params : SQ_LPARAN function_qopml_params_list SQ_RPARAN
        """
        t[0] = t[2]
    
    def function_qopml_params_list(self, t):
        """
        function_qopml_params_list : function_qop_param
                    | function_qopml_params_list function_qop_param
        """
        if len(t) > 2:
            t[0] = t[1] 
            t[0].append(t[2])
        else:
            t[0] = [t[1]]

    def function_qop_param(self, t):
        """
        function_qop_param : IDENTIFIER COLON identifiers_list
        """
        t[0] = (t[1], t[3])
    
    def _extend(self):
        
        self.parser.add_state('functions', 'inclusive')
        self.parser.add_state('functioncomment', 'exclusive')

        self.parser.add_reserved_word('functions', 'FUNCTIONS_SPECIFICATION', func=self.word_functions_specification,)
        self.parser.add_reserved_word('fun', 'FUN', func=self.word_fun, state='functions')

        self.parser.add_token('BLOCK_OPEN', func=self.token_block_open, states=['functions'])
        self.parser.add_token('BLOCK_CLOSE', func=self.token_block_close, states=['functions'])
        self.parser.add_token('LPARAN', func=self.token_lparan, states=['functions'])
        self.parser.add_token('RPARAN', regex=r'\)', states=['functions'])
        
        # Function comment State
        self.parser.add_token('error', func=self.token_funcomment_error, states=['functioncomment'], include_in_tokens=False)
        self.parser.add_token('ignore', " \t", states=['functioncomment'], include_in_tokens=False)
        self.parser.add_token('COMMENT', r'[-_A-Za-z0-9 ]+', states=['functioncomment'])  
        self.parser.add_token('RPARAN', func=self.token_funcomment_rparan, states=['functioncomment'])

        self.parser.add_rule(self.functions_specification)
        self.parser.add_rule(self.functions_list)
        self.parser.add_rule(self.function)
        self.parser.add_rule(self.function_comment)
        self.parser.add_rule(self.function_params)
        self.parser.add_rule(self.function_qopml_params)
        self.parser.add_rule(self.function_qopml_params_list)
        self.parser.add_rule(self.function_qop_param)
        

    