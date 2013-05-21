'''
Created on 14-05-2013

@author: Damian Rusinek <damian.rusinek@gmail.com>
'''
from qopml.interpreter.model import CallFunctionExpression, IdentifierExpression,\
    BooleanExpression
from qopml.interpreter.simulator import EnvironmentDefinitionException
from types import InstanceType

class Equation():
    """
    Equation built for simulation from parsed equation.
    """
    def __init__(self, composite, simple):
        self.composite = composite
        self.simple = simple

class Validator():
    
    def _find_function(self, functions, name):
        """"""
        for f in functions:
            if f.name == name:
                return f
        return None
    
    def _validate_function_names(self, expression, functions):
        """
        Method checs if all function exist and are callef woth correct number of parameters.
        Returns True or raises EnvironmentDefinitionException.
        """
        if isinstance(expression, CallFunctionExpression):
            function = self._find_function(functions, expression.function_name)
            if not function:
                raise EnvironmentDefinitionException('Function %s does not exist' % expression.function_name)
            if len(function.params) != len(expression.arguments):
                raise EnvironmentDefinitionException('Function %s called with wrong number of arguments - expected: %d, got: %d' 
                                                     % expression.function_name, len(function.params), len(expression.arguments))
            for arg in expression.arguments:
                if isinstance(arg, CallFunctionExpression):
                    self._validate_function_names(arg, functions)
        return True
    
    def _are_expressions_the_same(self, left, right, check_variables=False, variables={}):
        """
        Method checks if expressions are the same in aspect of equations, which means that
        both expressions could be used to reduce another expression.
        Method can check also the names variables from both expressions. Method checks 
        if variable X from left expression stands in all the same places (and no more) 
        that corresponding variable Y from right expressions.
        
        Example:
        f(x,y,x,x) == f(a,b,a,a) - are the same
        f(x,y,x,x) == f(a,b,a,b) - are not the same, because second b should be a
        """
        
        if type(left) != type(right):
            return False
        
        if isinstance(left, IdentifierExpression):
            if not check_variables:
                return True
            
            if left.identifier in variables:
                return variables[left.identifier] == right.identifier
            else:
                variables[left.identifier] = right.identifier
                return True
            
        if isinstance(left, BooleanExpression):
            return left.val == right.val
        
        if isinstance(left, CallFunctionExpression):
            
            if left.function_name != right.function_name:
                return False
            
            if len(left.arguments) != len(right.arguments):
                return False
            
            for i in range(0, len(left.arguments)):
                if not self._are_expressions_the_same(left.arguments[i], right.arguments[i], check_variables, variables):
                    return False
            return True
        
        return False
    
    def _validate_syntax(self, parsed_equations, functions):
        """
        Method check the syntax of equations:
        - does composite part include the identifier from simple part (if simple part is identifier)?
        - do all functions exist and are callef woth correct number of parameters?
        Returns True or raises EnvironmentDefinitionException.
        """
        errors = []
        for eq in parsed_equations:
            try:
                self._validate_function_names(eq.composite, functions)
            except EnvironmentDefinitionException, e:
                errors.append(e.args[0])
                
            if isinstance(eq.simple, IdentifierExpression):
                if not self._expression_contains_identifier(eq.simple.identifier):
                    errors.append("Equation '%s' does not have identifier from simple expression '%s' in composite expression."
                                  % (unicode(eq), eq.simple.identifier))
        if len(errors) > 0:
            raise EnvironmentDefinitionException('Invalid syntax', errors=errors)
    
    def validate(self, parsed_equations, functions):
        """
        Validates equations parsed from model according to functions.
        Returns True if validation is passed or raises EnvironmentDefinitionException.
        """
        
        # Validate syntax - function names and parametrs counts
        self._validate_syntax(parsed_equations)
        
        errors = []
        
        # Search for equations that can reduce themselves
        # Check all possible pairs of equations
        for i in range (0, len(parsed_equations)):
            has_the_same_expression = False
            for j in range(i+1, len(parsed_equations)):
                variables_map = {}
                eq_left = parsed_equations[i]
                eq_right = parsed_equations[j]
                
                if self._are_expressions_the_same(eq_left.composite, eq_right.composite, check_variables=True, variables=variables_map):
                    if variables_map[eq_left.simple.identifier] == eq_right.simple.identifier:
                        has_the_same_expression = True
                        break
            if has_the_same_expression:
                errors.append("Equations '%s' and '%s' are the same." % (unicode(eq_left), unicode(eq_right)))
        
        # Todo: Check ambiguity
        
        return True
