#!/usr/bin/env python
# simpatico.py
""" This is a complete rewrite of the old simpatico.
Hopefully it's good. """

import sys

#MOSS_INCLUDE_LOCATIONS

DEFAULT_TYPES = ['void', 'char', 'short', 'int', 'long',
                 'float', 'double', 'signed', 'unsigned']
IGNORABLE_KEYWORDS = ['auto', 'register', 'static',
                      'const', 'volatile']
KNOWN_VARIABLES = ['errno', 'stderr', 'stdout']
BINARY_OPERATORS = ["+", "/", "%", ">>", "<<", "|", "^", "->", ".", "?", ":"]
UNARY_OPERATORS = ["--", "++"]
LOGICAL_OPERATORS = ["&&", "||", "<", ">", "<=", ">=", "=="]
ASSIGNMENTS = ["=", "%=", "+=", "-=", "*=", "/=", "|=", "&=", "<<=", ">>="]
ALL_OPS = BINARY_OPERATORS + UNARY_OPERATORS + ASSIGNMENTS + LOGICAL_OPERATORS
#by the time we use this one, there's no natural \t chars left
COMMENT = '\t'

class Type(object):
    """ Yes, this could be an Enum, but I'm being kind to older versions of
    Python """
    (   ERROR_TYPE, DEFINE, INCLUDE, COMMENT, NEWLINE, COMMA, LBRACE, RBRACE,
        LPAREN, RPAREN, MINUS, BINARY_OPERATOR, LOGICAL_OPERATOR, STAR,
        AMPERSAND, TYPE, CREMENT, IGNORE, KW_EXTERN, BREAK, FOR, SWITCH, CASE,
        STRUCT, CONTINUE, TYPEDEF, RETURN, UNKNOWN, CONSTANT, WHILE, DO
    ) = range(31)

class Fragment(object):
    """ This is where we start getting funky with building the structure of
    the code. """
    def __init__(self, start_word):
        self.start_word = start_word

class Block(Fragment):
    """ For code blocks (e.g. { stuff }). """
    def __init__(self, start_word):
        Fragment.__init__(self, start_word)
        self.header = []
        self.tokens = []

class Statement(Fragment):
    """ Statements (i.e. stuff;) """
    def __init__(self, start_word):
        Fragment.__init__(self, start_word)
        self.tokens = []

class Word(object):
    """ Keeps track of contextual details about the word """
    def __init__(self):
        self.space = -1
        self.line_number = -1
        self.line = []
        self.start = -1
        self.type = Type.ERROR_TYPE

    def get_line_number(self):
        return self.line_number

    def get_string(self):
        return "".join(self.line)

    def get_position(self):
        return self.start

    def get_spacing_left(self):
        return self.space

    def append(self, char, space_left, line_number, char_location):
        if self.line_number == -1:
            self.line_number = line_number
            self.space = space_left
            self.start = char_location
        self.line.append(char)

    def empty(self):
        return len(self.line) == 0

    def finalise(self):
        """ here's where we work out what type of thing this word is """
        line = "".join(self.line)
        #prepare thyself for many, many elifs
        if line.lower() == "#define":
            self.type = Type.DEFINE
        elif line.lower() in ["#include", "#ifdef", "#ifndef", "#endif",
                "#undef"]:
            self.type = Type.INCLUDE
        elif line == "\t":
            self.type = Type.COMMENT
        elif line == "\n":
            self.type = Type.NEWLINE
        elif line == ",":
            self.type = Type.COMMA
        elif line == "{":
            self.type = Type.LBRACE
        elif line == "}":
            self.type = Type.RBRACE
        elif line == "(":
            self.type = Type.LPAREN
        elif line == ")":
            self.type = Type.RPAREN
        elif line == "-":
            self.type = Type.MINUS
        elif line in BINARY_OPERATORS:
            self.type = Type.BINARY_OPERATOR
        elif line in LOGICAL_OPERATORS:
            self.type = Type.LOGICAL_OPERATOR
        elif line == "*":
            self.type = Type.STAR
        elif line == "&":
            self.type = Type.AMPERSAND
        elif line in DEFAULT_TYPES:
            self.type = Type.TYPE
        elif line in ["--", "++"]:
            self.type = Type.CREMENT
        elif line in IGNORABLE_KEYWORDS:
            self.type = Type.IGNORE
        elif line == "extern":
            self.type = Type.KW_EXTERN
        elif line == "break":
            self.type = Type.BREAK
        elif line == "for":
            self.type = Type.FOR
        elif line == "do":
            self.type = Type.DO
        elif line == "while":
            self.type = Type.WHILE
        elif line == "switch":
            self.type = Type.SWITCH
        elif line == "case":
            self.type = Type.CASE
        elif line in ["struct", "union"]:
            self.type = Type.STRUCT
        elif line == "continue":
            self.type = Type.CONTINUE
        elif line == "typedef":
            self.type = Type.TYPEDEF
        elif line == "return":
            self.type = Type.RETURN
        elif line[0] == '"' or line[0] == "'" or line.isdigit():
            self.type = Type.CONSTANT
        else:
            self.type = Type.UNKNOWN #variables and externally defined types

    def get_type(self):
        return self.type

    def __repr__(self):
        return "%d:%d  i:%d '\033[1m%s\033[0m'\n" % (self.line_number,
                self.start, self.space, "".join(self.line))

class Tokeniser(object):
    DUPLICATE_OPS = ['|', '&', '<', '>', '+', '-', '=']
    """ The thing that turns a gigantic file of hopefully not terrible code
    into tokens that we can then deal with """
    def __init__(self, filename):
        self.tokens = []
        self.line_number = 1
        self.line_start = 0
        self.in_operator = False
        self.in_string = False
        self.in_char = False
        self.multi_char_op = False
        self.multiline_comment = 0
        self.in_singleline_comment = False
        self.deal_breakers = [' ', '.', '-', '+', '/', '*', '>', '<', '&',
                '|', '!', '~', '%', '^', '(', ')', '{', '}', ';', ',', ':',
                '?']
        self.current_word = Word()
        self.space_left = 0
        self.current_word_start = 1
        #well that was fun, now we should do some real work
        f = open(filename, "r")
        allllll_of_it = f.read().expandtabs(8)
        f.close()
        self.tokenise(allllll_of_it)

    def end_word(self):
        if self.current_word.empty():
            return
        self.current_word.finalise()
        self.tokens.append(self.current_word)
        self.current_word = Word()
        self.in_operator = False
        self.in_string = False
        self.in_char = False
        self.multi_char_op = False

    def add_to_word(self, char, n):
        self.current_word.append(char, self.space_left, self.line_number,
                self.current_word_start)
        self.space_left = 0

    def tokenise(self, megastring):
        """ Why yes, this is a big function. Be glad it's not the usual parser
        switch statement that's 1000 lines long. """
        for n, c in enumerate(megastring):
            #step 0: if we were waiting for the second char in a "==" or
            # similar, grab it and move on already
            if self.multi_char_op:
                self.add_to_word(c, n)
                #catch dem silly >>= and <<= ops
                if self.current_word.get_string() + c + "=" in ASSIGNMENTS:
                    continue
                self.end_word()
                continue
            #step 1: deal with the case of being in a //comment
            if self.in_singleline_comment:
                if c == '\n':
                    self.in_singleline_comment = False
                    self.add_to_word(COMMENT, n)
                    self.end_word()
                else:
                    continue

            #step 2: continue on while inside a multiline comment
            elif self.multiline_comment:
                #but update line numbers if it's a newline
                if c == '\n':
                    self.line_number += 1
                    self.line_start = n + 1
                #if we've reached the end of the comment
                if self.multiline_comment == n:
                    self.multiline_comment = 0
                    self.add_to_word(COMMENT, n)
                    self.end_word()
            #step 3: deal with newlines, ends the current word
            elif c == '\n':
                #out with the old
                self.end_word()
                #in with the new..
                self.line_number += 1
                self.line_start = n + 1
                #...line AHYUK, AHYUK
                self.add_to_word(c, n)
                self.end_word()

            #don't want to get caught interpreting chars in strings as real
            elif self.in_string:
                self.add_to_word(c, n)
                #string ending
                if c == '"':
                    #but not if it's escaped
                    if megastring[n-1] == '\\':
                        #make sure the slash wasn't itself escaped
                        if megastring[n-2] == '\\':
                            self.end_word()
                    else:
                        #eeennnd it, and escape this if tree
                        self.end_word()
            #that was fuuun, but it repeats with chars
            elif self.in_char:
                self.add_to_word(c, n)
                #first: is it a '; second: are sneaky people involved
                if c == "'" and megastring[n-1] != '\\':
                    self.end_word()
            #catch dem spaces
            elif c == ' ':
                self.end_word()
                self.space_left += 1

            #catch the start of a string
            elif c == '"':
                self.in_string = not self.in_string
                self.add_to_word(c, n)
            #or, for that matter, the start of a char
            elif c == "'":
                self.in_char = not self.in_char
                self.add_to_word(c, n)
            #now we just have to catch the possible word seperators
            elif c in self.deal_breakers:
                if c == "/" and megastring[n+1] == "*":
                    self.multiline_comment = megastring.find("*/", n) + 1
                elif c == "/" and megastring[n+1] == "/":
                    self.in_singleline_comment = True
                elif c + megastring[n+1] in ALL_OPS:
                    self.multi_char_op = True
                    self.end_word()
                    self.add_to_word(c, n)
                #ennnnd of ze word
                else:
                    self.end_word()
                    #only single character constructs remain, so add them and
                    #include "bad_jokes.h"
                    #... END THEM
                    self.add_to_word(c, n)
                    self.end_word()
            else:
                self.add_to_word(c, n)

    def get_tokens(self):
        return self.tokens

class Errors(object):
    (IF, ELSE, ELSEIF, RUNON, FUNCTION, GLOBALS, VARIABLE, TYPE,
            DEFINE) = range(9)
    """Everyone's favourite"""
    def __init__(self):
        self.naming_d = {}
        self.whitespace_d = {}
        self.comments_d = {}
        self.braces_d = {}
        self.line_length_d = {}
        self.func_length_d = {}
        self.total = 0

    def naming(self, token, name_type):
        self.total += 1
        msg = "WHOOPS"
        if name_type == Styler.TYPE:
            msg = " misnamed, types should be NamedLikeThis"
        elif name_type == Styler.FUNCTION:
            msg = " misnamed, functions should be named_like_this"
        elif name_type == Styler.DEFINE:
            msg = " misnamed, #defines should be NAMED_LIKE_THIS"
        elif name_type == Styler.VARIABLE:
            msg = " misnamed, variables should be namedLikeThis"
        self.naming_d[token.get_line_number()] = "[NAMING] " + \
                token.get_string() + msg

    def whitespace(self, token, expected):
        self.total += 1
        self.whitespace_d[token.get_line_number()] = "[WHITESPACE] At \
                position %d expected %d whitespace, had %d" % (
                token.get_position(), expected, token.get_spacing_left())

    def line_length(self, line_number, length):
        self.total += 1
        self.line_length_d[line_number] = "line is %d chars long" % length

    def func_length(self, line_number, length):
        self.total += 1
        self.func_length_d[line_number] = "[OVERALL] Function length of %d is \
                over the maximum of 50" % length

    def braces(self, token, error_type):
        self.total += 1
        msg = "WHOOPS"
        if error_type == Errors.IF:
            msg = ", if braces should look like: if (cond) {"
        elif error_type == Errors.ELSE:
            msg = ", else braces should look like: } else {"
        elif error_type == Errors.ELSEIF:
            msg = ", else if braces should look like: } else if (cond) {"
        elif error_type == Errors.RUNON:
            msg = ", braces should be the last character on the line"
        self.braces[token.get_line_number()] = "[BRACES] at position " + \
                token.get_position() + msg

    def comments(self, line_number, error_type):
        self.total += 1
        msg = "WHOOPS"
        if error_type == Errors.FUNCTION:
            msg = "Functions should be preceeded by explanatory comments"
        elif error_type == Errors.GLOBALS:
            msg = "Global variables should be commented"
        self.comments[line_number] = msg

    def get(self, line_number):
        result = []
        for error_type in [self.braces_d, self.whitespace_d,
                self.line_length_d, self.naming_d, self.func_length_d,
                self.comments_d]:
            result.extend(error_type.get(line_number, []))
        return result

    def __repr__(self):
        counts = [len(error_type.keys()) for error_type in [
                self.braces_d, self.whitespace_d,
                self.line_length_d, self.naming_d, self.func_length_d,
                self.comments_d]]
        for i in range(len(counts)):
            if counts[i] > 5:
                counts[i] = 5
        return "%d total errors found, " % self.total + \
                "B:%d W:%d C:%d N:%d O:%d L:%d (capped at 5 per type)" % \
                tuple(counts)

class Styler(object):
    MAX = False
    """ Where style violations are born """
    def __init__(self, filename, verbose = False, output_file = False):
        #some setup
        self.errors = Errors()

        #quick run for line lengths
        line_number = 0
        self.infile = open(filename, "r")
        for line in self.infile:
            if len(line) > 79:
                self.errors.line_length(line_number, len(line))
        self.infile.close()
        self.position = 0
        self.comments = {}
        #then the guts of it all
        tokeniser = Tokeniser(filename)
        self.tokens = tokeniser.get_tokens()
        self.current_token = self.tokens[self.position]
        try:
            self.process_globals(filename)
        except IndexError as e:
            #that'd be us finished
            pass

        if output_file:
            self.write_output_file(filename)

        if verbose:
            print self.errors

    def match(self):
        self.position += 1
        #unsafe, deliberately so
        self.current_token = self.tokens[self.position]
        while self.current_token.get_type() == Type.COMMENT:
            self.comments[self.current_token.get_line_number()] = True
            self.match()

    def previous_token(self):
        return self.tokens[self.position - 1]

    def peek(self):
        try:
            return self.tokens[self.position + 1]
        except IndexError as e:
            return Word()

    def write_output_file(self, filename):
        """go over the file and insert messages when appropriate"""
        line_number = 1
        outf = open(filename+".style", "w")
        infile = open(filename, "r")
        for line in infile:
            outf.writelines(self.errors.get(line_number))
        infile.close()
        outf.close()

    def process_globals(self, filename):
        """ There's an assumption here that the code compiles to start with.
        Only checking the types of tokens that can start lines in this
        context (compiler directives, prototypes, declarations, definitions).
        """
        i = self.position
        expected_indent = 0 #at global level
        while True:
            token = self.current_token
            self.check_whitespace(token, expected_indent);
            self.match()
            tokentype = token.get_type()
            #check for compiler directives that aren't #define
            if token.type == Type.INCLUDE:
                #just strip these out, we don't care
                while self.current_token.get_type() != Type.NEWLINE:
                    self.match()
            #define
            elif token.type == Type.DEFINE:
                self.check_define()
            #declaration
            elif token.type == Type.TYPE:
                self.check_declaration()
            elif token.type == Type.IGNORE:
                self.check_declaration()
            #spare whitespace
            elif token.type == Type.NEWLINE:
                #skip leading blank lines
                #TODO maybe violate multiples
                continue
            elif token.type == Type.UNKNOWN:
                self.check_statement()
            else:
                print "found an awkward type in global space:", token

    def check_whitespace(self, token, expected, is_strict = True):
        if is_strict:
            if token.get_spacing_left() != expected:
                self.errors.whitespace(token, expected)
        else:
            if token.get_spacing_left() <= expected:
                self.errors.whitespace(token, expected)

    def check_naming(self, token, name_type = Errors.VARIABLE):
        name = token.get_string()
        if name_type == Errors.VARIABLE:
            if "_" in name or len(name) == 1 and name.isupper():
                self.errors.naming(token, name_type)
        elif name_type == Errors.FUNCTION:
            for c in name:
                if c.isupper():
                    self.errors.naming(token, name_type)
                    break
        elif name_type == Errors.TYPE:
            if "_" in name or not name[0].isupper():
                self.errors.naming(token, name_type)
        elif name_type == Errors.DEFINE:
            if not name.isupper():
                self.errors.naming(token, name_type)
        else:
            print "check_naming(): unknown naming type given: token=", token

    def check_for(self):
        print "check_for(): not implemented"

    def check_while(self):
        print "check_while(): not implemented"

    def check_do(self):
        print "check_do(): not implemented"

    def check_switch(self):
        print "check_switch(): not implemented"

    def check_case(self):
        print "check_case(): not implemented"

    def check_statement(self):
        print "check_statement(): not implemented"

    def check_block(self):
        self.depth += 1
        print "check_block(): not implemented"
        token = self.current_token
        #since this is a opening brace, ensure we have a following newline
        if token.type != Type.NEWLINE:
            self.errors.braces(token, Errors.RUNON)
            self.match()
            token = self.current_token
        #block ends if we hit the matching brace
        while token.type != Type.RBRACE:
            self.check_whitespace(token)
            self.match()
            if token.type == Type.RETURN:
                self.check_expression()
            elif token.type == Type.CREMENT:
                self.check_statement()
            elif token.type == Type.FOR:
                self.check_for()
            elif token.type == Type.WHILE:
                self.check_while()
            elif token.type == Type.DO:
                self.check_do()
            elif token.type == Type.SWITCH:
                self.check_switch()
            elif token.type != Type.NEWLINE:
                continue
            else:
                print "check_block(): unexpected token:", token
        self.depth -= 1
        self.check_whitespace(token)
        return

    def check_define(self):
        print "check_define(): not implemented"

    def check_paren(self):
        while True:
            token = self.current_token
            self.match()
            if token.type == Type.RPAREN:
                return
            #possibly:
            # function prototype
            # function definition
            if token.type == Type.TYPE:
                #finish the type
                pass
            # function call
            # typecast
            # expression
            else:
                print "check_paren(): unexpected token:", token

    def check_declaration(self):
        terminator = None
        expected_indent = 1
        while True:
            token = self.current_token
            self.match()
            if token.type == terminator:
                return
            # check indentation
            self.check_whitespace(token, expected_indent)
            # continue checking
            if token.type == Type.TYPE:
                self.check_declaration()
            if token.type == Type.STAR:
                #found a pointer declaration
                self.check_whitespace(token, 1, Styler.MAX)
                name = self.tokens[i+1] #TODO check if newline
            if token.type == Type.UNKNOWN:
                #sounds like a variable name
                pass #TODO
            if token.type == Type.IGNORE:
                pass
            else:
                print "check_declaration(): unexpected type:", token

if __name__ == '__main__':
    if (len(sys.argv)) == 1:
        print "no arguments given"
    for i in range(1, len(sys.argv)):
        if sys.argv[i].strip():
            print 'Parsing %s...' % sys.argv[i],
            style = Styler(sys.argv[i])
            print style.errors

