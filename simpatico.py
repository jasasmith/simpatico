#!/usr/bin/env python
# simpatico.py
""" This is a complete rewrite of the old simpatico.
Hopefully it's good. """


import sys

DEFAULT_TYPES = ['void', 'char', 'short', 'int', 'long',
                 'float', 'double', 'signed', 'unsigned']
IGNORABLE_KEYWORDS = ['auto', 'register', 'static',
                      'const', 'volatile']
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
        STRUCT, CONTINUE, TYPEDEF, RETURN
    ) = range(27)

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

    def get_start_position(self):
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
        elif line.lower() == "#include":
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

    def get_type(self):
        return self.type

    def __repr__(self):
        return "%d:%d  i:%d '%s'\n" % (self.line_number, self.start,
                                     self.space, "".join(self.line))

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
                if c == '#' and not self.tokens:
                    self.hash_line = True
                self.add_to_word(c, n)

    def get_tokens(self):
        return self.tokens

class Styler:
    """ Where style violations are born """
    def __init__(self, filename, verbose = False, output_file = False):
        #some setup
        self.errors = {}

        #quick run for line lengths
        line_number = 0
        self.infile = open(filename, "r")
        for line in self.infile:
            if len(line) > 79:
                self.errors[line_number] = \
                        "[LINE-LENGTH] Line is %d characters long" % len(line)
        self.comment_lines = {}
        #then the guts of it all
        self.process(filename)

        self.infile.close()

        if output_file:
            self.write_output_file(filename)

        if verbose:
            self.print_errors()

    def print_errors(self):
        #and a little message for people, this could be extended
        if self.errors:
            print "style violations found"
        else:
            print "celebrate"

    def write_output_file(self, filename):
        """go over the file and insert messages when appropriate"""
        line_number = 1
        outf = open(filename+".style", "w")
        infile = open(filename, "r")
        for line in infile:
            if len(line.expandtabs()) > 79:
                outf.write("[LINE-LENGTH] Line is %d characters long" \
                        % len(line))
            outf.writelines(self.errors.get(line_number, []))
        infile.close()
        outf.close()

    def process(self, filename):
        tokeniser = Tokeniser(filename)
        tokens = tokeniser.get_tokens()
        constructs = []
        current_construct = []
        for i in xrange(len(tokens)):
            token = tokens[i]

if __name__ == '__main__':
    for i in range(1, len(sys.argv)):
        if sys.argv[i].strip():
            print 'Parsing %s...' % sys.argv[i],
            token = Tokeniser(sys.argv[i])
            print token.get_tokens()

