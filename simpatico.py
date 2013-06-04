#!/usr/bin/env python
# simpatico.py
""" This is a complete rewrite of the old simpatico.
Hopefully it's good. """

import sys

#MOSS_INCLUDE_LOCATIONS

DEBUG = True

INDENT_SIZE = 4
LINE_CONTINUATION_SIZE = 8
ALLOW_ZERO = True
(NO_NEWLINE, MAY_NEWLINE, MUST_NEWLINE) = range(3)
IS_TYPEDEF = True

def d(elements):
    if DEBUG:
        print " ".join([str(x) for x in elements])

DEFAULT_TYPES = ['void', 'char', 'short', 'int', 'long',
                 'float', 'double', 'signed', 'unsigned']
IGNORABLE_KEYWORDS = ['auto', 'register', 'static',
                      'const', 'volatile']
KNOWN_VARIABLES = ['errno', 'stderr', 'stdout']
BINARY_OPERATORS = ["+", "/", "%", ">>", "<<", "|", "^", "->", ".", "?", ":"]
UNARY_OPERATORS = ["--", "++", "!"]
LOGICAL_OPERATORS = ["&&", "||", "<", ">", "<=", ">=", "=="]
ASSIGNMENTS = ["=", "%=", "+=", "-=", "*=", "/=", "|=", "&=", "<<=", ">>="]
ALL_OPS = BINARY_OPERATORS + UNARY_OPERATORS + ASSIGNMENTS + LOGICAL_OPERATORS
#by the time we use this one, there's no natural \t chars left
COMMENT = '\t'

class Type(object):
    """ Yes, this could be an Enum, but I'm being kind to older versions of
    Python """
    ANY = -1
    (   ERROR_TYPE, DEFINE, INCLUDE, COMMENT, NEWLINE, COMMA, LBRACE, RBRACE,
        LPAREN, RPAREN, MINUS, BINARY_OP, LOGICAL_OP, STAR,
        AMPERSAND, TYPE, CREMENT, IGNORE, KW_EXTERN, BREAK, FOR, SWITCH, CASE,
        STRUCT, CONTINUE, TYPEDEF, RETURN, UNKNOWN, CONSTANT, WHILE, DO,
        SEMICOLON, COLON, TERNARY, ASSIGNMENT, IF, ELSE, LSQUARE, RSQUARE,
        LINE_CONT, DEFAULT, NOT
    ) = range(42)

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
        self.whitespace_checked = 0

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
        elif line == "if":
            self.type = Type.IF
        elif line == "else":
            self.type = Type.ELSE
        elif line == "\t":
            self.type = Type.COMMENT
        elif line == ";":
            self.type = Type.SEMICOLON
        elif line == "!":
            self.type = Type.NOT
        elif line in ASSIGNMENTS:
            self.type = Type.ASSIGNMENT
        elif line == "\n":
            self.type = Type.NEWLINE
        elif line == ",":
            self.type = Type.COMMA
        elif line == "{":
            self.type = Type.LBRACE
        elif line == "?":
            self.type = Type.TERNARY
        elif line == ":":
            self.type = Type.COLON
        elif line == "}":
            self.type = Type.RBRACE
        elif line == "(":
            self.type = Type.LPAREN
        elif line == ")":
            self.type = Type.RPAREN
        elif line == "-":
            self.type = Type.MINUS
        elif line in BINARY_OPERATORS:
            self.type = Type.BINARY_OP
        elif line in LOGICAL_OPERATORS:
            self.type = Type.LOGICAL_OP
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
            self.type = Type.RETURN
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
        elif line == "default":
            self.type = Type.DEFAULT
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
        elif line == "[":
            self.type = Type.LSQUARE
        elif line == "]":
            self.type = Type.RSQUARE
        elif line == "\\":
            self.type = Type.LINE_CONT
        else:
            d(["D: finalise() could not match type for", self])
            self.type = Type.UNKNOWN #variables and externally defined types

    def __repr__(self):
        return "%d:%d  i:%d '\033[1m%s\033[0m'" % (self.line_number,
                self.start, self.space, "".join(self.line))

class Tokeniser(object):
    """ The thing that turns a gigantic file of hopefully not terrible code
    into tokens that we can then deal with """
    DUPLICATE_OPS = ['|', '&', '<', '>', '+', '-', '=']
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
                '?', '[', ']']
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
        self.current_word.append(char, self.space_left, self.line_number, n)
        self.space_left = 0

    def tokenise(self, megastring):
        """ Why yes, this is a big function. Be glad it's not the usual parser
        switch statement that's 1000 lines long. """
        for n, c in enumerate(megastring):
            #step 0: if we were waiting for the second char in a "==" or
            # similar, grab it and move on already
            if self.multi_char_op:
                self.add_to_word(c, n - self.line_start)
                #catch dem silly >>= and <<= ops
                if self.current_word.get_string() + "=" in ASSIGNMENTS:
                    continue
                self.end_word()
                continue
            #step 1: deal with the case of being in a //comment
            if self.in_singleline_comment:
                if c == '\n':
                    self.in_singleline_comment = False
                    self.add_to_word(COMMENT, n - self.line_start)
                    self.end_word()
                    #then add the newline
                    self.add_to_word(c, n - self.line_start)
                    self.end_word()
                    self.line_number += 1
                    self.line_start = n + 1
                else:
                    continue

            #step 2: continue on while inside a multiline comment
            elif self.multiline_comment:
                #if we've reached the end of the comment
                if self.multiline_comment == n:
                    self.multiline_comment = 0
                    self.add_to_word(COMMENT, n - self.line_start)
                    self.end_word()
                #but update line numbers if it's a newline
                if c == '\n':
                    self.line_number += 1
                    self.line_start = n + 1
            #step 3: deal with newlines, ends the current word
            elif c == '\n':
                #out with the old
                self.end_word()
                #in with the new..
                self.line_number += 1
                self.line_start = n + 1
                #...line AHYUK, AHYUK
                self.add_to_word(c, n - self.line_start)
                self.end_word()

            #don't want to get caught interpreting chars in strings as real
            elif self.in_string:
                self.add_to_word(c, n - self.line_start)
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
                self.add_to_word(c, n - self.line_start)
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
                self.add_to_word(c, n - self.line_start)
            #or, for that matter, the start of a char
            elif c == "'":
                self.in_char = not self.in_char
                self.add_to_word(c, n - self.line_start)
            #now we just have to catch the possible word seperators
            elif c in self.deal_breakers:
                if c == "/" and megastring[n+1] == "*":
                    self.multiline_comment = megastring.find("*/", n) + 1
                elif c == "/" and megastring[n+1] == "/":
                    self.in_singleline_comment = True
                elif c + megastring[n+1] in ALL_OPS:
                    self.end_word()
                    self.multi_char_op = True
                    self.add_to_word(c, n - self.line_start)
                #ennnnd of ze word
                else:
                    self.end_word()
                    #only single character constructs remain, so add them and
                    #include "bad_jokes.h"
                    #... END THEM
                    self.add_to_word(c, n - self.line_start)
                    self.end_word()
            else:
                self.add_to_word(c, n - self.line_start)

    def get_tokens(self):
        return self.tokens

class Errors(object):
    (IF, ELSE, ELSEIF, RUNON, FUNCTION, GLOBALS, VARIABLE, TYPE,
            DEFINE, MISSING, CLOSING) = range(11)
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
        if name_type == Errors.TYPE:
            msg = " misnamed, types should be NamedLikeThis"
        elif name_type == Errors.FUNCTION:
            msg = " misnamed, functions should be named_like_this"
        elif name_type == Errors.DEFINE:
            msg = " misnamed, #defines should be NAMED_LIKE_THIS"
        elif name_type == Errors.VARIABLE:
            msg = " misnamed, variables should be namedLikeThis"
        self.naming_d[token.line_number] = "[NAMING] " + \
                token.get_string() + msg

    def whitespace(self, token, expected):
        self.total += 1
        assert token.get_spacing_left() != expected
        self.whitespace_d[token.line_number] = "[WHITESPACE] At " + \
                "position %d: expected %d whitespace, found %d " % (
                token.get_position(), expected, token.get_spacing_left())

    def line_length(self, line_number, length):
        self.total += 1
        self.line_length_d[line_number] = "line is %d chars long" % length

    def func_length(self, line_number, length):
        self.total += 1
        self.func_length_d[line_number] = "[OVERALL] Function length of" \
                + " %d is over the maximum of 50" % length

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
            msg = ", a brace should be the last character on the line"
        elif error_type == Errors.MISSING:
            msg = ", braces are required, even for single line blocks"
        self.braces_d[token.line_number] = \
                "[BRACES] at position %d%s" % (token.get_position(), msg)

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

    def print_lines(self):
        for error_type in [self.braces_d, self.whitespace_d,
                self.line_length_d, self.naming_d, self.func_length_d,
                self.comments_d]:
            for key in sorted(error_type.keys()):
                print "line", key, ":", error_type[key]

    def __repr__(self):
        if not self.total:
            return "no errors found"
        counts = [len(error_type.keys()) for error_type in [
                self.braces_d, self.whitespace_d,
                self.line_length_d, self.naming_d, self.func_length_d,
                self.comments_d]]
        for i in range(len(counts)):
            if counts[i] > 5:
                counts[i] = 5
        return " ".join(["%d total errors found," % self.total,
                "B:%d W:%d C:%d N:%d O:%d L:%d" % \
                tuple(counts), "(capped at 5/type and 1/type/line)"])

class Styler(object):
    MAX = False
    """ Where style violations are born """
    def __init__(self, filename, verbose = True, output_file = False):
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
        self.depth = 0
        self.comments = {}
        self.line_continuation = False
        #then the guts of it all
        tokeniser = Tokeniser(filename)
        self.tokens = tokeniser.get_tokens()
        self.current_token = self.tokens[self.position]
        try:
            while self.current_token.type in [Type.NEWLINE, Type.COMMENT]:
                d(["pre-process: skipping newline/comment", self.current_token])
                if self.current_token.type == Type.COMMENT:
                    self.check_whitespace()
                    self.comments[self.current_token.line_number] = True
                self.position += 1
                self.current_token = self.tokens[self.position]
            self.process_globals(filename)
        except IndexError:
            #that'd be us finished
            pass
        #make sure no changes skip whitespace
        if DEBUG:
            for token in self.tokens:
                if token.type not in [Type.NEWLINE, Type.LINE_CONT] \
                        and token.whitespace_checked != 1:
                    print "whitespace check %d:" % token.whitespace_checked, token

                    
        if output_file:
            self.write_output_file(filename)

        if verbose:
            self.errors.print_lines()

    def match(self, req_type = Type.ANY, post_newline = NO_NEWLINE,
            pre_newline = NO_NEWLINE):
        #store interesting parts
        old = self.current_token
        # ensure we're matching what's expected
        if req_type != Type.ANY and old.type != req_type:
            print "match fail:", self.current_token, old.type, req_type
            assert old.type == req_type
       # do a whitespace check for semicolons
        if old.type == Type.SEMICOLON:
            if self.previous_token().type == [Type.COMMENT, Type.NEWLINE]:
                self.check_whitespace(self.depth * INDENT_SIZE)
            else:
                self.check_whitespace(0)
        # check pre-token newlines if {}
        elif old.type in [Type.LBRACE, Type.RBRACE]:
            # previous was a newline but shouldn't have been
            if self.previous_token().type in [Type.NEWLINE, Type.COMMENT]:
                if pre_newline == NO_NEWLINE:
                    self.errors.braces(self.current_token, Errors.IF)
            else: #previous wasn't a newline but should've been
                if pre_newline == MUST_NEWLINE:
                    self.errors.braces(self.current_token, Errors.RUNON)
        #update
        self.position += 1
        self.current_token = self.tokens[self.position] #deliberately unsafe
        
        # clear comments
        while self.current_token.type == Type.COMMENT:
            self.comments[self.current_token.line_number] = True
            self.position += 1
            self.current_token = self.tokens[self.position]
       
        # check for extra post-token newlines
        if post_newline == NO_NEWLINE and self.current_token.type \
                in [Type.NEWLINE, Type.LINE_CONT, Type.COMMENT]:
            if old.type == Type.RBRACE:
                self.errors.braces(old, Errors.RUNON)
            elif old.type != Type.SEMICOLON:
                self.line_continuation = True
        # check for missing post-token newlines
        elif post_newline == MUST_NEWLINE \
                and self.current_token.type not in [Type.NEWLINE,
                Type.LINE_CONT, Type.COMMENT]:
            self.errors.braces(self.previous_token(), Errors.RUNON)
        # consume all the newlines that may or may not have been there
        while self.current_token.type in [Type.NEWLINE, Type.LINE_CONT]:
            self.position += 1
            self.current_token = self.tokens[self.position]

    def check_whitespace(self, expected = -1, one_or_zero = not ALLOW_ZERO):
        token = self.current_token
        if expected == -1:
            expected = self.depth * INDENT_SIZE
        if self.line_continuation and token.type != Type.RBRACE:
            expected = self.depth * INDENT_SIZE + LINE_CONTINUATION_SIZE
        if token.whitespace_checked and DEBUG:
            print "whitespace check duplicated:", token
            token.whitespace_checked += 1
            return
        token.whitespace_checked += 1
        if one_or_zero and expected <= 1:
            if token.get_spacing_left() > 1:
                d(["whitespace \033[1m error \033[0m:", expected, token,
                        self.depth])
                self.errors.whitespace(token, expected)
        elif token.get_spacing_left() != expected:
            d(["whitespace \033[1merror\033[0m:", expected, token,
                    self.depth])
            self.errors.whitespace(token, expected)
        if self.line_continuation:
            self.line_continuation = False

    def previous_token(self):
        return self.tokens[self.position - 1]

    def peek(self):
        i = self.position + 1
        while self.tokens[i].type in [Type.COMMENT, Type.NEWLINE,
                Type.LINE_CONT]:
            i += 1
        return self.tokens[i]
    
    def has_matching_else(self):
        i = self.position + 1
        depth = 1
        try:
            while self.tokens[i].type not in [Type.IF, Type.RPAREN,
                    Type.RBRACE, Type.ELSE]:
                i += 1
                if self.tokens[i].type == Type.RBRACE:
                    depth -= 1
                    if depth >= 0:
                        i += 1
            return self.tokens[i].type == Type.ELSE
        except IndexError:
            return False

    def write_output_file(self, filename):
        """go over the file and insert messages when appropriate"""
        line_number = 1
        outf = open(filename+".style", "w")
        infile = open(filename, "r")
        for line in infile:
            outf.writelines(self.errors.get(line_number))
        infile.close()
        outf.close()

    def consume_line(self):
        while self.current_token.type != Type.NEWLINE:
            self.position += 1
            self.current_token.type = self.tokens[self.position]

    def process_globals(self, filename):
        """ There's an assumption here that the code compiles to start with.
        Only checking the types of tokens that can start lines in this
        context (compiler directives, prototypes, declarations, definitions).
        """
        while True:
            if self.current_token.type != Type.SEMICOLON:
                self.check_whitespace(0)
            #check for compiler directives that aren't #define
            if self.current_token.type == Type.INCLUDE:
                self.match()
#TODO           #just strip these out, we don't care for now
                self.consume_line()
            #define
            elif self.current_token.type == Type.DEFINE:
                self.match()
                self.check_define()
            #declaration
            elif self.current_token.type in [Type.TYPE, Type.UNKNOWN]:
                self.check_declaration()
            #type qualifiers
            elif self.current_token.type == Type.IGNORE:
                self.match()
                self.check_declaration()
            #skippable
            elif self.current_token.type in [Type.NEWLINE, Type.COMMENT]:
                self.match(Type.ANY, MUST_NEWLINE)
                continue
            #struct definition/declaration
            elif self.current_token.type == Type.STRUCT:
                self.match()
                self.check_struct()
            #typedef
            elif self.current_token.type == Type.TYPEDEF:
                self.match()
                self.check_typedef()
            #ruh roh
            else:
                 print "found an awkward type in global space:", \
                         self.current_token
                self.match()

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

    def check_struct(self, isTypedef = False):
        d(["D: check_struct() entered"])
        #skip the type name
        if self.current_token.type == Type.UNKNOWN:
            self.check_whitespace(1)
            self.match(Type.UNKNOWN) # indentifier
        #ensure it's the block, then start it
        assert self.current_token.type == Type.LBRACE
        self.check_whitespace(1)
        self.match(Type.LBRACE, MAY_NEWLINE, MAY_NEWLINE)
        self.check_block()
        self.match(Type.RBRACE, MAY_NEWLINE, MAY_NEWLINE)
        if not isTypedef:
            self.match(Type.SEMICOLON, MUST_NEWLINE)
        d(["D: check_struct() exited", self.current_token])

    def check_typedef(self):
        d(["D: check_typedef() entered", self.current_token])
        if self.current_token.type == Type.STRUCT:
            self.check_whitespace(1)
            self.match(Type.STRUCT)
            self.check_struct(IS_TYPEDEF)
            self.check_whitespace(1)
            self.match(Type.UNKNOWN) # type
        else:
            while self.current_token.type in [Type.TYPE, Type.UNKNOWN]:
                self.check_whitespace(1)
                self.match() # type
        self.match(Type.SEMICOLON, MUST_NEWLINE)
        d(["D: check_typedef() exited", self.current_token])

    def check_for(self):
        self.match(Type.LPAREN) # (
        self.check_whitespace(0)
        d(["D:checking for init", self.current_token])
        self.check_statement(NO_NEWLINE) #for (thing;
        d(["checking for conditional", self.current_token])
        self.check_whitespace(1)
        self.check_expression() #for (thing; thing
        self.match(Type.SEMICOLON)
        self.check_whitespace(1)
        d(["checking for post-loop", self.current_token])
        self.check_expression() #for (thing; thing; thing)
        while self.current_token.type == Type.COMMA:
            self.check_expression() #for (thing; thing; thing, ...)
        if self.current_token.type == Type.LBRACE:
            self.check_whitespace(1)
            self.match(Type.LBRACE, MUST_NEWLINE)
            self.check_block()
            self.match(Type.RBRACE, MUST_NEWLINE, MUST_NEWLINE)
        else:
            self.errors.braces(self.current_token, Errors.MISSING)
            self.check_whitespace((self.depth + 1) * INDENT_SIZE)
            self.check_statement()

    def should_have_block(self, is_chained = False):
        if self.current_token.type == Type.LBRACE:
            self.check_whitespace(1)
            self.match(Type.LBRACE, MUST_NEWLINE)
            self.check_block()
            if is_chained:
                self.match(Type.RBRACE, NO_NEWLINE, MUST_NEWLINE)
            else:
                self.match(Type.RBRACE, MUST_NEWLINE, MUST_NEWLINE)
        else:
            self.check_whitespace((self.depth + 1) * INDENT_SIZE)
            self.errors.braces(self.current_token, Errors.MISSING)
            self.check_statement()

    def check_condition(self):
        # check spacing on the parenthesis
        self.check_whitespace(1) # if/while (
        self.match(Type.LPAREN)
        self.check_whitespace(0) # (exp
        self.check_expression()
        self.check_whitespace(0) # exp)
        self.match(Type.RPAREN)

    def check_do(self):
        self.match(Type.LBRACE, MUST_NEWLINE)
        self.check_block()
        self.match(Type.RBRACE, NO_NEWLINE, MUST_NEWLINE)
        self.match(Type.WHILE)
        self.match(Type.LPAREN)
        if self.current_token.type != Type.RPAREN:
            self.check_expression() # exp )
        self.match(Type.RPAREN)
        self.match(Type.SEMICOLON, MUST_NEWLINE)

    def check_switch(self):
        d(["D:check_switch(): entered", self.current_token])
        self.match(Type.LPAREN)
        self.check_whitespace(0)
        self.check_expression()
        self.check_whitespace(0)
        self.match(Type.RPAREN)
        self.check_whitespace(1)
        self.match(Type.LBRACE, MUST_NEWLINE)
        self.depth += 1
        while self.current_token.type == Type.CASE:
            self.check_whitespace(self.depth * INDENT_SIZE)
            self.match(Type.CASE)
            self.check_whitespace(1)
            self.match(Type.CONSTANT)
            self.check_whitespace(0)
            self.match(Type.COLON, MUST_NEWLINE)
            self.check_case()
        if self.current_token.type == Type.DEFAULT:
            self.check_whitespace(self.depth * INDENT_SIZE)
            self.match(Type.DEFAULT)
            self.check_whitespace(0)
            self.match(Type.COLON, MUST_NEWLINE)
            self.check_case()
        self.depth -= 1
        self.check_whitespace(self.depth * INDENT_SIZE)
        self.match(Type.RBRACE, MUST_NEWLINE, MUST_NEWLINE)
        d(["D:check_switch(): exited", self.current_token])

    def check_case(self):
        d(["D:check_case(): entered", self.current_token])
        while self.current_token.type not in [Type.CASE, Type.DEFAULT]:
            if self.current_token.type == Type.RBRACE:
                if self.previous_token().type != Type.NEWLINE:
                    self.errors.braces(self.current_token.type, Errors.CLOSING)
                break
            self.check_whitespace((self.depth + 1) * INDENT_SIZE)
            self.check_statement()
        d(["D:check_case(): exited", self.current_token])

    def check_statement(self, in_for = False):
        d(["D: check_statement(): entered", self.current_token])
        if self.current_token.type == Type.TYPE:
            self.check_declaration()
        elif self.current_token.type == Type.UNKNOWN:
            self.match(Type.UNKNOWN)
        if self.current_token.type == Type.ASSIGNMENT:
            self.check_whitespace(1)
            self.match(Type.ASSIGNMENT)
            self.check_whitespace(1)
            self.check_expression()
            while self.current_token.type == Type.COMMA:
                self.check_whitespace(0)
                self.match(Type.COMMA)
                self.check_whitespace(1)
#TODO: this will break, surely
                assert self.current_token.type == Type.UNKNOWN
        elif self.current_token.type == Type.LPAREN:
            self.match(Type.LPAREN)
            #function call
            self.check_expression()
            while self.current_token.type == Type.COMMA:
                self.match(Type.COMMA)
                self.check_whitespace(1)
                self.check_expression()
            self.match(Type.RPAREN)
        elif self.current_token.type == Type.RETURN:
            self.match(Type.RETURN)
            #return value?
            if self.current_token.type != Type.SEMICOLON:
                self.check_whitespace(1)
                self.check_expression()
        elif self.current_token.type == Type.CREMENT:
            self.check_whitespace(0)
            self.match(Type.CREMENT)
        self.match(Type.SEMICOLON, not in_for)
        d(["D: check_statement(): exited", self.current_token])


    def check_expression(self):
        d(["D: check_exp(): entered", self.current_token])
        #clear out any pre-value modifiers
        if self.current_token.type == Type.AMPERSAND:
            self.match(Type.AMPERSAND)
            self.check_whitespace(0)
        elif self.current_token.type == Type.STAR:
            self.match(Type.MINUS)
            self.check_whitespace(0)
        elif self.current_token.type == Type.MINUS:
            self.match(Type.MINUS)
            self.check_whitespace(0)
        elif self.current_token.type == Type.CREMENT:
            self.match(Type.CREMENT)
            self.check_whitespace(0)
        elif self.current_token.type == Type.LPAREN:
            self.match(Type.LPAREN)
            self.check_whitespace(0)
            #match a whole new expression
            self.check_expression()
        elif self.current_token.type == Type.NOT:
            self.match(Type.NOT)
            self.check_whitespace(0)
        elif self.current_token.type == Type.RPAREN:
            #end this
            self.match(Type.RPAREN)
            return
        elif self.current_token.type not in [Type.UNKNOWN, Type.CONSTANT]:
            d(["D: check_exp(): unexpected token:", self.current_token])

        #grab a value of some form
        while self.current_token.type in [Type.UNKNOWN, Type.CONSTANT]:
            self.match() #the value
            #check if it was a function, check if it's being called
            if self.current_token.type == Type.LPAREN:
                self.check_whitespace(0)
                self.match(Type.LPAREN)
                self.check_whitespace(0)
                #does it have args
                if self.current_token.type != Type.RPAREN:
                    #process first arg
                    self.check_expression()
                    #process others, if they exist
                    while self.current_token.type == Type.COMMA:
                        self.check_whitespace(0)
                        self.match(Type.COMMA)
                        self.check_whitespace(1)
                        self.check_expression()
                self.check_whitespace(0)
                self.match(Type.RPAREN)
            # now grab the operators before the next value
            while self.current_token.type in [Type.CREMENT, Type.BINARY_OP,
                    Type.LOGICAL_OP, Type.MINUS]:
                self.check_whitespace(1, ALLOW_ZERO)
                self.match() #'-- / - &&' etc
                self.check_whitespace(1, ALLOW_ZERO)
                self.check_expression()
        d(["D: check_exp(): exited", self.current_token])

    def check_block(self):
        d(["\nD: check_block(): entered", self.current_token])
        self.depth += 1
        #block ends if we hit the matching brace
        while self.current_token.type != Type.RBRACE:
            d(["D:in block while: ", self.current_token])
            self.check_whitespace(self.depth * INDENT_SIZE)
            if self.current_token.type == Type.TYPE:
                self.match(Type.TYPE)
                self.check_whitespace(1)
                self.check_declaration()
                if self.current_token.type == Type.SEMICOLON:
                    self.match(Type.SEMICOLON, MUST_NEWLINE)
            elif self.current_token.type == Type.RETURN:
                self.match(Type.RETURN)
                if self.current_token.type != Type.SEMICOLON:
                    self.check_whitespace(1)
                    self.check_expression()
                self.match(Type.SEMICOLON, MUST_NEWLINE)
            elif self.current_token.type == Type.CREMENT:
                self.match(Type.CREMENT)
                self.check_whitespace(0)
                self.match(Type.UNKNOWN) # identifier
                self.match(Type.SEMICOLON, MUST_NEWLINE)
            elif self.current_token.type == Type.FOR:
                self.match(Type.FOR)
                self.check_whitespace(1)
                self.check_for()
            elif self.current_token.type == Type.WHILE:
                self.match(Type.WHILE)
                self.check_condition()
                self.should_have_block()
            elif self.current_token.type == Type.DO:
                self.match(Type.DO)
                self.check_do()
            elif self.current_token.type == Type.SWITCH:
                self.match(Type.SWITCH)
                self.check_whitespace(1)
                self.check_switch()
            elif self.current_token.type == Type.SEMICOLON:
                self.match(Type.SEMICOLON, MUST_NEWLINE)
            elif self.current_token.type == Type.IF:
                self.match(Type.IF)
                self.check_condition()
                self.should_have_block(self.has_matching_else())
                while self.current_token.type == Type.ELSE:
                    self.check_whitespace(1)
                    self.match(Type.ELSE)
                    if self.current_token.type == Type.IF:
                        self.check_whitespace(1)
                        self.match(Type.IF)
                        self.check_condition()
                        self.should_have_block(self.has_matching_else())
                    else:
                        self.should_have_block(self.has_matching_else())
            elif self.current_token.type == Type.UNKNOWN:
                self.match(Type.UNKNOWN)
                self.check_statement()
            else:
                print "check_block(): unexpected token:", self.current_token
                self.match()
        self.depth -= 1
        self.check_whitespace(self.depth * INDENT_SIZE)
        d(["D: check_block(): exited", self.current_token, "\n"])

    def check_define(self):
#TODO 
        print "check_define(): not properly implemented"
        while self.current_token.type != Type.NEWLINE:
            self.position += 1
            self.current_token = self.tokens[i]
            
        self.position += 1
        self.current_token = self.tokens[i]

    def check_array_assignment(self):
        if self.current_token.type == Type.UNKNOWN:
            #assignment is to another variable
            self.check_whitespace(1)
            self.match() # identifier
            return
        self.match(Type.LBRACE, MAY_NEWLINE)
        self.check_whitespace(0)
        self.check_expression()
        while self.current_token.type == Type.COMMA:
            self.check_whitespace(0)
            self.match(Type.COMMA)
            if self.current_token.type == Type.LINE_CONT: # /
#TODO: more checking here, probs
                self.check_whitespace(1)
                self.match(Type.LINE_CONT)
            else:
                self.check_whitespace(1)
            self.check_expression()
        self.check_whitespace(0)
        self.match(Type.RBRACE, MAY_NEWLINE, MAY_NEWLINE)
        assert self.current_token.type == Type.SEMICOLON

    def check_declaration(self):
        d(["D:check_declaration() entered", self.current_token])
        array = False
        #skip all the potential types and modifiers
        while self.current_token.type != Type.UNKNOWN:
            d(["D:decl: consuming:", self.current_token])
            self.match() #type/modifier
            self.check_whitespace(1)
        self.match(Type.UNKNOWN)
        #is this a function?
        if self.current_token.type == Type.LPAREN:
            d(["D:decl is a func", self.previous_token()])
            self.check_naming(self.previous_token(), Errors.FUNCTION)
            self.check_whitespace(0)
            self.match(Type.LPAREN)
            if self.current_token.type != Type.RPAREN:
                self.check_whitespace(0)
                print "consuming without checking:", self.current_token
                self.match()
#TODO need to chomp some args here and test naming
            #but for now
            while self.current_token.type != Type.RPAREN:
                if self.current_token.type == Type.COMMA:
                    self.check_whitespace(0)
                else:
                    self.check_whitespace(1)
                self.match() #args
            self.check_whitespace(0)
            self.match(Type.RPAREN)
            #was it just a prototype
            if self.current_token.type == Type.SEMICOLON:
                self.match(Type.SEMICOLON, MUST_NEWLINE)
            #and now for the hard one
            elif self.current_token.type == Type.LBRACE:
                start_line = self.current_token.line_number
                self.check_whitespace(1)
                self.match(Type.LBRACE, MUST_NEWLINE, MAY_NEWLINE)
                self.check_block()
                self.match(Type.RBRACE, MUST_NEWLINE, MUST_NEWLINE)
                func_length = self.current_token.line_number - start_line
                if func_length >= 50:
                    self.errors.func_length(start_line, func_length)
            d(["D:check_declaration() exited", self.current_token])
            return
        d(["D:decl is a var", self.previous_token()])
        #well, it's a non-func then
        self.check_naming(self.previous_token(), Errors.VARIABLE)
        #is it an array?
        if self.current_token.type == Type.LSQUARE:
            self.check_whitespace(0)
            self.match(Type.LSQUARE)
            self.check_expression()
            self.check_whitespace(0)
            self.match(Type.RSQUARE)
            array = True
        #if this isn't initialised
        if self.current_token.type == Type.SEMICOLON:
            #leave the semicolon matching for the parent check_statement()
            d(["D:check_declaration() exited", self.current_token])
            return
            
        #token will now be , or =
        if self.current_token.type == Type.ASSIGNMENT:
            self.check_whitespace(1)
            self.match(Type.ASSIGNMENT)
            self.check_whitespace(1)
            if array:
                self.check_array_assignment()
                assert self.current_token.type == Type.SEMICOLON
            else:
                self.check_expression()
        
        #is it a multi-var declaration?
        while self.current_token.type == Type.COMMA:
            self.check_whitespace(0)
            self.match(Type.COMMA)
            self.check_whitespace(1)
            #is it another identifier?
            assert self.current_token.type == Type.UNKNOWN
            self.match() #identifier
            #or was the previous identifier being initialised
            if self.current_token.type == Type.ASSIGNMENT:
                self.check_whitespace(1)
                self.match(Type.ASSIGNMENT)
                self.check_whitespace(1)
                self.check_expression() #match out the expression
                continue
        assert self.current_token.type == Type.SEMICOLON
        d(["D:check_declaration() exited", self.current_token])
            
if __name__ == '__main__':
    if (len(sys.argv)) == 1:
        print "no arguments given"
    for i in range(1, len(sys.argv)):
        if sys.argv[i].strip():
            print 'Parsing %s...' % sys.argv[i],
            style = Styler(sys.argv[i])
            print style.errors

