# #############################################################################
# MDTraj: A Python Library for Loading, Saving, and Manipulating
# Molecular Dynamics Trajectories.
# Copyright 2012-2014 Stanford University and the Authors
#
# Authors: Matthew Harrigan
# Contributors:
#
# MDTraj is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation, either version 2.1
# of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with MDTraj. If not, see <http://www.gnu.org/licenses/>.
# #############################################################################

from pyparsing import (Word, alphas, nums, oneOf, Group, infixNotation, opAssoc,
                       Keyword, MatchFirst, ParseException,
                       Optional, quotedString)



# Allow decimal numbers
nums += '.'


def _kw(*tuples):
    """Create a many-to-one dictionary.

    _kw((['one', '1'], 'one'))
    gives {'one': 'one', '1': 'one'}
    """
    dic = dict()
    for keys, val in tuples:
        for key in keys:
            dic[key] = val
    return dic


def _cast(value, add_quotes=False):
    """Try to cast values into a number. Return string otherwise."""
    try:
        # Is it an int?
        val = int(value)
    except ValueError:
        # Not an int. What about a float?
        try:
            val = float(value)
        except ValueError:
            # Not a float. What about a complex?
            try:
                val = complex(value)
            except ValueError:
                # Not any sort of number. Let's strip quotes though
                val = value.strip("\"'")
                if add_quotes:
                    val = "'{}'".format(val)
    return val


class Operand(object):
    keyword_aliases = {}

    def mdtraj_condition(self):
        """Build an mdtraj-compatible piece of python code."""
        raise NotImplementedError

    def filter(self):
        raise NotImplementedError

    @classmethod
    def get_keywords(cls):
        raise NotImplementedError


class SelectionOperand(Operand):
    @classmethod
    def get_keywords(cls):
        keywords = sorted(cls.keyword_aliases.keys())
        return MatchFirst([Keyword(kw) for kw in keywords])

    @classmethod
    def get_top_item(cls):
        """Get the name of the appropriate topology field for mdtraj.

        E.g.: for atoms it is a.whatever and for residues it
        is a.residue
        """
        raise NotImplementedError

    @classmethod
    def get_top_name(cls):
        raise NotImplementedError

    @classmethod
    def accessor(cls):
        raise NotImplementedError


class UnaryOperand(SelectionOperand):
    """Single keyword selection identifier."""

    def __init__(self, tokes):
        tokes = tokes[0]
        self.value = tokes

    def mdtraj_condition(self):
        fmt_string = "{pre}.{value}"
        fmt_dict = dict(pre=self.get_top_item(),
                        value=self.keyword_aliases[self.value])
        return fmt_string.format(**fmt_dict)

    def filter(self):
        field = self.keyword_aliases[self.value]
        return lambda a: getattr(self.accessor()(a), field)

    __str__ = mdtraj_condition
    __repr__ = __str__


class AtomUnaryOperand(UnaryOperand):
    keyword_aliases = _kw(
        (['all', 'everything'], 'all'),
        (['none', 'nothing'], 'none')
    )

    @classmethod
    def get_top_item(cls):
        return 'a'

    @classmethod
    def get_top_name(cls):
        return 'Atom'

    @classmethod
    def accessor(cls):
        return lambda a: a


class ResidueUnaryOperand(UnaryOperand):
    """Single keyword selections that specify residues"""

    keyword_aliases = _kw(
        (['protein', 'is_protein'], 'is_protein'),
        (['nucleic', 'is_nucleic'], 'is_nucleic'),
        (['backbone', 'is_backbone'], 'is_backbone'),
        (['sidechain', 'is_sidechain'], 'is_sidechain'),
        (['water', 'waters', 'is_water'], 'is_water')
    )

    @classmethod
    def get_top_item(cls):
        return 'a.residue'

    @classmethod
    def get_top_name(cls):
        return 'Residue'

    @classmethod
    def accessor(cls):
        return lambda a: a.residue


class BinaryOperand(SelectionOperand):
    """Selection of the form: field operator value"""

    operator_aliases = _kw(
        (['<', 'lt'], ('<', '__lt__')),
        (['==', 'eq'], ('==', '__eq__')),
        (['<=', 'le'], ('<=', '__le__')),
        (['!=', 'ne'], ('!=', '__ne__')),
        (['>=', 'ge'], ('>=', '__ge__')),
        (['>', 'gt'], ('>', '__gt__'))
    )

    def __init__(self, tokes):
        tokes = tokes[0]
        if len(tokes) == 3:
            self.key, self.in_op, self.value = tokes
        else:
            err = "Binary selectors take 3 values. You gave {}"
            err = err.format(len(tokes))
            raise ParseException(err)

    @property
    def operator(self):
        """Return an operator lambda"""
        return lambda x: getattr(x, self.operator_aliases[self.in_op][1])

    @property
    def operator_str(self):
        """Return an operator string"""
        return self.operator_aliases[self.in_op][0]

    def mdtraj_range_condition(self):
        """Use special logic for constructing a range condition."""
        field = self.keyword_aliases[self.key]
        fmt_string = "{top}.{field}"
        fmt_dict = dict(top=self.get_top_item(), field=field)
        full_field = fmt_string.format(**fmt_dict)
        return self.value.range_condition(full_field, self.operator_str)

    def mdtraj_singleval_condition(self):
        """Normal condition for comparing to one value."""
        field = self.keyword_aliases[self.key]
        fmt_string = "{top}.{field} {op} {value}"
        fmt_dict = dict(top=self.get_top_item(), field=field,
                        op=self.operator_str,
                        value=_cast(self.value, add_quotes=True))
        return fmt_string.format(**fmt_dict)

    def mdtraj_condition(self):
        if isinstance(self.value, RangeOperand):
            return self.mdtraj_range_condition()
        else:
            return self.mdtraj_singleval_condition()

    def filter(self):
        field = self.keyword_aliases[self.key]
        field_attr = lambda x: getattr(self.accessor()(x), field)
        val = _cast(self.value)

        return lambda a: self.operator(field_attr(a))(val)

    __str__ = mdtraj_condition
    __repr__ = __str__


class ElementBinaryOperand(BinaryOperand):
    keyword_aliases = _kw(
        (['type', 'element'], 'symbol'),
        (['radius'], 'radius'),
        (['mass'], 'mass')
    )

    @classmethod
    def get_top_name(cls):
        return "Element"

    @classmethod
    def get_top_item(cls):
        return "a.element"

    @classmethod
    def accessor(cls):
        return lambda a: a.element


class AtomBinaryOperand(BinaryOperand):
    keyword_aliases = _kw(
        (['name'], 'name'),
        (['index', 'id'], 'index'),
        (['numbonds'], 'num_bonds'),
        (['within'], 'within')
    )

    @classmethod
    def get_top_name(cls):
        return 'Atom'

    @classmethod
    def get_top_item(cls):
        return 'a'

    @classmethod
    def accessor(cls):
        return lambda a: a


class ResidueBinaryOperand(BinaryOperand):
    """Selections that specify residues."""

    keyword_aliases = _kw(
        (['residue', 'resSeq'], 'resSeq'),
        (['resname'], 'name'),
        (['resid'], 'index')
    )

    @classmethod
    def get_top_name(cls):
        return 'Residue'

    @classmethod
    def get_top_item(cls):
        return 'a.residue'

    @classmethod
    def accessor(cls):
        return lambda a: a.residue


class RangeOperand:
    """Values of the form: first to last"""

    def __init__(self, tokes):
        tokes = tokes[0]
        if len(tokes) == 3:
            self.first, self.to, self.last = tokes

    def __str__(self):
        return "range({first} {to} {last})".format(**self.__dict__)

    __repr__ = __str__

    def range_condition(self, field, op):
        if self.to == 'to' and op == '==':
            pass
            return "{first} <= {field} <= {last}".format(
                first=self.first, field=field, last=self.last
            )
        else:
            # We may want to be able to do more fancy things later on
            # For example: "mass > 5 to 10" could be parsed (even though
            # it's kinda stupid)
            raise ParseException("Incorrect use of ranged value")


class InfixOperand(Operand):
    # Overwrite the following in base classes.
    num_terms = -1
    assoc = None

    @classmethod
    def get_keywords(cls):
        # Prepare tuples for pyparsing.infixNotation
        keywords = sorted(cls.keyword_aliases.keys())
        return [(kw, cls.num_terms, cls.assoc, cls) for kw in keywords]


class BinaryInfix(InfixOperand):
    """Deal with binary infix operators: and, or, etc"""

    num_terms = 2
    assoc = opAssoc.LEFT

    keyword_aliases = _kw(
        (['or', '||'], ('or', 'any')),
        (['and', '&&'], ('and', 'all')),
        (['of'], ('of', 'NotImplementedError'))
    )

    @property
    def operator(self):
        builtin = self.keyword_aliases[self.in_op][1]
        return lambda x: __builtins__[builtin](x)

    @property
    def operator_str(self):
        return self.keyword_aliases[self.in_op][0]

    def __init__(self, tokes):
        tokes = tokes[0]
        if len(tokes) % 2 == 1:
            self.in_op = tokes[1]
            self.parts = tokes[::2]
        else:
            err = "Invalid number of infix expressions: {}"
            err = err.format(len(tokes))
            raise ParseException(err)

    def filter(self):
        return lambda a: self.operator([p.filter()(a) for p in self.parts])

    def mdtraj_condition(self):

        # Join all the parts
        middle = " {} ".format(self.operator_str).join(
            [p.mdtraj_condition() for p in self.parts])

        # Put parenthesis around it
        return "({})".format(middle)

    __str__ = mdtraj_condition
    __repr__ = __str__


class NotInfix(InfixOperand):
    """Deal with unary infix operators: not"""

    num_terms = 1
    assoc = opAssoc.RIGHT

    keyword_aliases = _kw(
        (['not', '!'], 'not')
    )

    def __init__(self, tokes):
        tokes = tokes[0]
        if len(tokes) == 2:
            self.in_op, self.value = tokes
        else:
            err = "Invalid number of expressions for not operation: {}"
            err = err.format(len(tokes))
            raise ParseException(err)


    def mdtraj_condition(self):
        return "({} {})".format(self.operator_str,
                                self.value.mdtraj_condition())

    @property
    def operator_str(self):
        return self.keyword_aliases[self.in_op]

    def filter(self):
        return lambda a: not self.value.filter()(a)

    __str__ = mdtraj_condition
    __repr__ = __str__


class SelectionParser(object):
    def __init__(self, select_string=None):
        self.parser = _make_parser()

        if select_string is not None:
            self.last_parse = self.parser.parseString(select_string)[0]
        else:
            # Default to all atoms
            self.last_parse = self.parser.parseString("all")[0]


    def parse(self, select_string):
        """Parse a selection string."""

        # We need to select element zero of the result of parseString
        # I don't know what would ever go in the rest of the list.
        self.last_parse = self.parser.parseString(select_string)[0]
        return self

    @property
    def mdtraj_condition(self):
        return self.last_parse.mdtraj_condition()

    @property
    def filter(self):
        return self.last_parse.filter()


def _make_parser():
    """Build an expression that can parse atom selection strings."""

    # Single Keyword
    # - Atom
    single_atom = AtomUnaryOperand.get_keywords()
    single_atom.setParseAction(AtomUnaryOperand)
    # - Residue
    single_resi = ResidueUnaryOperand.get_keywords()
    single_resi.setParseAction(ResidueUnaryOperand)

    # Key Value Keywords
    # - A value is a number, word, or range
    numrange = Group(Word(nums) + "to" + Word(nums))
    numrange.setParseAction(RangeOperand)
    value = numrange | Word(nums) | quotedString | Word(alphas)

    # - Operators
    comparison_op = oneOf(list(BinaryOperand.operator_aliases.keys()))
    comparison_op = Optional(comparison_op, '==')

    # - Atom
    binary_atom = Group(
        AtomBinaryOperand.get_keywords() + comparison_op + value)
    binary_atom.setParseAction(AtomBinaryOperand)
    # - Residue
    binary_resi = Group(
        ResidueBinaryOperand.get_keywords() + comparison_op + value)
    binary_resi.setParseAction(ResidueBinaryOperand)
    # - Element
    elem_resi = Group(
        ElementBinaryOperand.get_keywords() + comparison_op + value)
    elem_resi.setParseAction(ElementBinaryOperand)

    # Put it together
    expression = MatchFirst([
        single_atom, single_resi, binary_atom, binary_resi, elem_resi
    ])

    # And deal with logical expressions
    logical_expr = infixNotation(expression, (
        BinaryInfix.get_keywords() + NotInfix.get_keywords()
    ))
    return logical_expr