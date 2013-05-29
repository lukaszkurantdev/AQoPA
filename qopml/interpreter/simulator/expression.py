'''
Created on 07-05-2013

@author: Damian Rusinek <damian.rusinek@gmail.com>
'''
import copy
from qopml.interpreter.model import IdentifierExpression, CallFunctionExpression, TupleExpression
from qopml.interpreter.simulator.error import RuntimeException

class Checker():
    """
    Expression checker.
    Class used to check the result of expressions.
    """
    
    def populate_variables(self, expression, variables):
        """
        Returns new expression with replaced variables names 
        with copies of values of variables from variables list.
        """
        if isinstance(expression, IdentifierExpression):
            if expression.identifier not in variables:
                raise RuntimeException("Variable '%s' does not exist" % expression.identifier)
            return variables[expression.identifier].clone()
            
        if isinstance(expression, CallFunctionExpression):
            arguments = []
            for arg in expression.arguments:
                arguments.append(self.populate_variables(arg, variables))
            qop_arguments = []
            for qop_arg in expression.qop_arguments:
                qop_arguments.append(qop_arg)
            return CallFunctionExpression(expression.function_name, arguments, qop_arguments)
            
        if isinstance(expression, TupleExpression):
            elements = []
            for e in expression.elements:
                elements.append(self.populate_variables(e, variables))
            return TupleExpression(elements)
        
        return expression.clone()
    
    
    def result(self, condition, variables, functions):
        raise NotImplementedError()

class ReductionPoint():
    """
    Class representing point where expression can be reduced.
    """
    
    def __init__(self, equation, expression, replacement, modified_part=None, modified_element_info=None):
        
        self.equation       = equation      # Equation that is used to reduce
        self.expression     = expression    # Expression that will be reduced
                                            # Reduction can replace whole expression 
                                            # or the part of expression
        self.replacement    = replacement   # Expression that will replace reduced part
        self.replaced = None                # Part of expression that was replaced with replacement
                                
        self.modified_part          = modified_part         # Part of expression that will be modified
                                                            # If None, whole expression should be replaced
        self.modified_element_info  = modified_element_info # Information which element 
                                                            # of modified part should be replaced
        
    def _get_replaced_part(self):
        """
        Returns the part of expression that will be replaced.
        """
        if isinstance(self.modified_part, CallFunctionExpression):
            return self.modified_part.arguments[self.modified_element_info]
        
    def _replace_part(self, replacement):
        """
        Replace the part of modified_part according to modified_element_info.
        """
        if isinstance(self.modified_part, CallFunctionExpression):
            self.modified_part.arguments[self.modified_element_info] = replacement
        
    def reduce(self):
        """
        Returns reduced expression. 
        Method saves informaction for rolling back the reduction.
        """ 
        if self.modified_part is None:
            return self.replacement 
        
        self.replaced = self._get_replaced_part()
        self._replace_part(self.replacement)
        return self.expression
        
    def rollback(self):
        """
        Rolls back the reduction. 
        Returns expression to the form before reduction. 
        """
        if self.modified_part is None:
            return self.expression
        
        self._replace_part(self.replaced)
        self.replaced = None
        return self.expression

class Reducer():
    """
    Expression reducer.
    Class used to recude complex expressions with usage of equations.
    """
    
    def __init__(self, equations):
        self.equations = equations
        
        
    def _get_reduction_points_for_equation(self, equation, whole_expression, current_expression, 
                                           parent_expression=None, modified_element_info=None):
        """
        Recursive strategy of finding points.
        """
        points = []
        variables = {}
        
        if equation._can_reduce(current_expression, equation.composite, variables):
            
            if isinstance(equation.simple, IdentifierExpression):
                simpler_value = variables[equation.simple.identifier]
            else:
                simpler_value = equation.simple
                
            points.append(ReductionPoint(equation, 
                                         expression=whole_expression, 
                                         replacement=simpler_value, 
                                         modified_part=parent_expression, 
                                         modified_element_info=modified_element_info))
        
        if isinstance(current_expression, CallFunctionExpression):
            
            for i in range(0, len(current_expression.arguments)):
                e = current_expression.arguments[i]
                for p in self._get_reduction_points_for_equation(equation, 
                                                                 whole_expression, 
                                                                 current_expression=e,
                                                                 parent_expression=current_expression,
                                                                 modified_element_info=i):
                    points.append(p)
        
        return points
        
    def get_reduction_points_for_equation(self, equation, expression):
        """
        Method returns list of points where equation can reduce expression.
        
        Example:
        equation:   f(x) = x
        expression: f(a(f(b())))
                    ^   ^
        Two reduction points selected above,
        """
        return self._get_reduction_points_for_equation(equation=equation, 
                                          whole_expression=expression, 
                                          current_expression=expression,
                                          parent_expression=None,
                                          modified_element_info=None)
        
    def _get_reduction_points(self, expression):
        """
        Method finds points in expression where it can be reduced.
        """
        points = []
        for eq in self.equations:
            for p in self.get_reduction_points_for_equation(eq, expression):
                points.append(p)
        return points
        
    def reduce(self, expression):
        """
        Reduces expression with usage of equations.
        Returns True if expression is reduced or False if it is not reducable.
        Raises exception if ambiguity is found.
        """
        reduced = False
        continue_reducing = True
   
        """     
        # Wrap expression and user wrapper variable
        # Used to simulate real pass-by-reference
        # If expression was passed without wrapped variable and equation wanted to
        # replace whole exception, it would not work, because whole variable cannot be changed
        # For example:
        # eq enc(K, dec(K, X)) = X
        # expression: enc(k(), dec(k(), b()) should be reduced to b()
        # If we pass whole expression variable to reduce we cannot change it whole
        # def f(x,v) -> x = v
        # e = A(a=1)
        # f(e, A(a=2)) - will not work, because e is reference to instance, but passed by value
        # When we pass wrapper, we can change its element (ie. expression)
        """
        
        # Reduce until no reduction can be performed.
        # One reduction can give way for another reduction.
        while continue_reducing:
            continue_reducing = False
            
            # For each equation we find points where expression can be reduced
            reduction_points = self._get_reduction_points(expression)
        
            if len(reduction_points) > 0:
                
                # For each poing:
                #  - temporary reduce at this point
                #  - remove used point from reduction points list
                #  - generate new reduction points list for reduced expression
                #  - if any of points from old list is not present in new list raise ambiguity exception
                #  ! New reduction points may come
                
                for reduction_point in reduction_points:
                    
                    # Generate list with reduction points before reduction
                    old_reduction_points = copy.copy(reduction_points)
                    old_reduction_points.remove(reduction_point)
                    
                    # Reduce temporary
                    expression = reduction_point.reduce()
                    
                    # Generate new reduction points
                    new_reduction_points = self._get_reduction_points(expression)
                    
                    for old_reduction_point in old_reduction_points:
                        found = False
                        for new_reduction_point in new_reduction_points:
                            if old_reduction_point.equals_to(new_reduction_point):
                                found = True
                                break
                        if not found:
                            raise RuntimeException("Equations '%s' and '%s are ambiguous" % 
                                                   (unicode(old_reduction_point.equation),
                                                    unicode(new_reduction_point.equation)))
                            
                    # Cancel reduction
                    expression = reduction_point.rollback()
                    
                # Ambiguity error checked
                    
                # Make factual reduction
                reduction_point = reduction_points[0]
                
                # Reduce and commit reduction
                expression = reduction_point.reduce()
                
                reduced = True
                continue_reducing = True
             
            return reduced
                
                
                
                
                
                