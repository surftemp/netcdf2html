# MIT License
#
# Copyright (C) 2023-2024 University of Reading
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software
# and associated documentation files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
# BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


class ExpressionParser:

    class ParseError(Exception):

        def __init__(self, error_type, error_position, error_content):
            super().__init__(error_type)
            self.error_type = error_type
            self.error_position = error_position
            self.error_content = error_content

    def __init__(self):
        self.input = None
        self.unary_operators = {}
        self.binary_operators = {}
        self.reset()

    def reset(self):
        # lexer state
        self.index = 0
        self.tokens = []
        self.current_token_type = None # s_string, d_string, string, name, operator, number, open_parenthesis, close_parenthesis, comma
        self.current_token_start = 0
        self.current_token = None

    def add_unary_operator(self, name):
        self.unary_operators[name] = True

    def add_binary_operator(self, name, precedence):
        self.binary_operators[name] = precedence

    def is_alphanum(self, c):
        return self.is_alpha(c) or (c >= "0" and c <= "9")

    def is_alpha(self, c):
        return ((c >= "a" and c <= "z") or (c >= "A" and c <= "Z"))

    def flush_token(self):
        if self.current_token_type is not None:
            if self.current_token_type == "name":
                # convert to name => operator if the name matches known operators
                if self.current_token in self.binary_operators or self.current_token in self.unary_operators:
                    self.current_token_type = "operator"


            self.tokens.append([self.current_token_type, self.current_token, self.current_token_start])

        self.current_token = ""
        self.current_token_type = None
        self.current_token_start = None

    def read_whitespace(self, c):
        t = self.current_token_type
        if t == "s_string" or t == "d_string":
            self.current_token += c
        elif t == "name" or t == "operator" or t == "number":
            self.flush_token()

    def read_doublequote(self):
        t = self.current_token_type

        if t == "d_string":
            self.flush_token()
        elif t == "s_string":
            self.current_token += '"'
        else:
            self.flush_token()
            self.current_token_type = "d_string"
            self.current_token_start = self.index


    def read_singlequote(self):
        t = self.current_token_type
        if t == "s_string":
            self.flush_token()
        elif t == "d_string":
            self.current_token += "'"
        else:
            self.flush_token();
            self.current_token_type = "s_string"
            self.current_token_start = self.index

    def read_digit(self,c):
        t = self.current_token_type

        if t == "operator":
            self.flush_token()
            self.current_token_type = "number"
            self.current_token_start = self.index
            self.current_token = c
        elif t is None:
            self.current_token_type = "number"
            self.current_token_start = self.index
            self.current_token = c
        elif t == "d_string" or t == "s_string" or t == "name" or t == "number":
            self.current_token += c

    def read_e(self, c):
        t = self.current_token_type
        if t == "number":
            # detect exponential notation E or e
            self.current_token += c
            # special case, handle negative exponent eg 123e-10
            if self.input[self.index+1] == "-":
                self.current_token += "-"
                self.index += 1
        else:
            self.read_default(c)

    def read_parenthesis(self, c):
        t = self.current_token_type
        if t == "s_string" or t == "d_string":
            self.current_token += c
        else:
            self.flush_token()
            self.tokens.append(["open_parenthesis" if c == "(" else "close_parenthesis",c, self.index])

    def read_comma(self, c):
        t = self.current_token_type
        if t == "d_string" or t == "s_string":
            self.current_token += c
        else:
            self.flush_token()
            self.tokens.append(["comma",c, self.index]);

    def read_default(self, c):
        t = self.current_token_type
        if t == "d_string" or t == "s_string":
            self.current_token += c
        elif t == "name":
            if self.is_alphanum(c) or c == "_" or c == ".":
                self.current_token += c
            else:
                self.flush_token()
                self.current_token_type = "operator"
                self.current_token_start = self.index
                self.current_token = c
        elif t == "number":
            self.flush_token()
            # todo handle exponential notation eg 1.23e10
            if self.is_alphanum(c):
                raise ExpressionParser.ParseError("invalid_number",self.index,c)
            else:
                self.flush_token()
                self.current_token_type = "operator"
                self.current_token_start = self.index
                self.current_token = c
        elif t == "operator":
            if self.is_alphanum(c):
                self.flush_token()
                self.current_token_type = "name"
                self.current_token_start = self.index
                self.current_token = c
            else:
                if self.current_token in self.unary_operators or self.current_token in self.binary_operators:
                    self.flush_token()
                    self.current_token_type = "operator"
                    self.current_token_start = self.index

                self.current_token += c
        elif t is None:
            self.current_token = c
            if self.is_alpha(c):
                self.current_token_type = "name"
            else:
                self.current_token_type = "operator"

            self.current_token_start = self.index
        else:
            raise ExpressionParser.ParseError("internal_error",self.index,"")

    def read_eos(self):
        t = self.current_token_type
        if t == "d_string" or t == "s_string":
            raise ExpressionParser.ParseError("unterminated_string",len(self.input),"")
        else:
            self.flush_token()

    def merge_string_tokens(self):
        merged_tokens = []
        buff = ""
        buff_pos = -1;
        for idx in range(len(self.tokens)):
            t = self.tokens[idx]
            ttype = t[0]
            tcontent = t[1]
            tstart = t[2]
            if ttype == "s_string" or ttype == "d_string":
                buff += tcontent
                buff_pos = tstart if (buff_pos < 0) else buff_pos
            else:
                if buff_pos >= 0:
                    merged_tokens.append(["string",buff,buff_pos])
                    buff = ""
                    buff_pos = -1

                merged_tokens.append(t)

        if buff_pos >= 0:
            merged_tokens.append(["string", buff, buff_pos])

        self.tokens = merged_tokens

    def lex(self):
        self.reset()
        self.index = 0
        while self.index < len(self.input):
            c = self.input[self.index]
            if c in [" ", "\t", "\n"]:
                self.read_whitespace(c)
            elif c == "\"":
                self.read_doublequote()
            elif c == "'":
                self.read_singlequote()
            elif c in ["(", ")"]:
                self.read_parenthesis(c)
            elif c == ",":
                self.read_comma(c)
            elif c in ["0","1","2","3","4","5","6","7","8","9","."]:
                self.read_digit(c)
            elif c in ["e","E"]:
                self.read_e(c)
            else:
                self.read_default(c)

            self.index += 1

        self.read_eos()
        self.merge_string_tokens()
        return self.tokens


    def get_ascending_precedence(self):
        prec_list = []
        for op in self.binary_operators:
            prec_list.append(self.binary_operators[op])

        prec_list = list(set(prec_list))

        prec_list = sorted(prec_list)

        return prec_list

    def parse(self, s):
        self.input = s
        try:
            self.lex()
            self.token_index = 0
            parsed = self.parse_expr()
            self.strip_debug(parsed)
            return parsed
        except Exception as ex:
            return ex

    def get_parser_context(self):
        return {
            "type": self.tokens[self.token_index][0],
            "content": self.tokens[self.token_index][1],
            "pos": self.tokens[self.token_index][2],
            "next_type":  self.tokens[self.token_index+1][0] if (self.token_index < (len(self.tokens) - 1)) else None,
            "last_type": self.tokens[self.token_index-1][0] if (self.token_index > 0) else None
        }

    def parse_function_call(self, name):
        ctx = self.get_parser_context()
        result = {
            "function": name,
            "args": [],
            "pos": ctx["pos"]
        }
        # skip over function name and open parenthesis
        self.token_index += 2

        # special case - no arguments
        ctx = self.get_parser_context()
        if ctx["type"] == "close_parenthesis":
            return result

        while(self.token_index < len(self.tokens)):
            ctx = self.get_parser_context()
            if ctx["last_type"] == "close_parenthesis":
                return result
            else:
                if ctx["type"] == "comma":
                   raise ExpressionParser.ParseError("comma_unexpected",ctx["pos"],"")

                # read an expression and a following comma or close parenthesis
                result["args"].append(self.parse_expr())

        return result

    def parse_expr(self):
        args = []
        while(self.token_index < len(self.tokens)):
            ctx = self.get_parser_context()
            t = ctx["type"]
            if t == "name":
                if ctx["next_type"] == "open_parenthesis":
                    args.append(self.parse_function_call(ctx["content"]))
                else:
                    self.token_index += 1
                    args.append({"name":ctx["content"],"pos":ctx["pos"]})
            elif t == "string":
                args.append({"literal":ctx["content"],"pos":ctx["pos"]})
                self.token_index += 1
            elif t == "number":
                args.append({"literal":float(ctx["content"]),"pos":ctx["pos"]})
                self.token_index += 1
            elif t == "open_parenthesis":
                self.token_index += 1
                args.append(self.parse_expr())
            elif t == "close_parenthesis" or t == "comma":
                self.token_index += 1;
                return self.refine_expr(args,self.token_index-1)
            elif t == "operator":
                args.append({"operator":ctx["content"],"pos":ctx["pos"]})
                self.token_index += 1

        return self.refine_expr(args,self.token_index)


    def refine_binary(self,args):
        precedences = self.get_ascending_precedence()
        for precedence_idx in range(len(precedences)):
            precedence = precedences[precedence_idx]
            idx=len(args)-2
            while idx>=0:
                subexpr = args[idx]
                if "operator" in subexpr and self.binary_operators[subexpr["operator"]] == precedence:
                    lhs = args[0:idx]
                    rhs = args[idx+1:]
                    e = {"operator":subexpr["operator"],"pos":subexpr["pos"],
                            "args":[self.refine_binary(lhs),self.refine_binary(rhs)]}
                    return e
                idx -= 2

        return args[0]


    def refine_expr(self, args,end_pos):
        if len(args) == 0:
            raise ExpressionParser.ParseError("expression_expected", end_pos,"")

        # first deal with unary operators
        i=len(args)-1
        while i>=0:
            # unary operators
            arg = args[i]
            prev_arg = args[i-1] if (i>0) else None
            next_arg = args[i+1] if (i<len(args)-1) else None
            if "operator" in arg and arg["operator"] in self.unary_operators:
                if prev_arg is None or "operator" in prev_arg:
                    if next_arg is not None:
                        # special case, convert unary - followed by a number literal to a negative number literal
                        if arg.get("operator","") == "-" and (isinstance(next_arg["literal"],float) or isinstance(next_arg["literal"],int)):
                            args = args[0:i]+[{
                                "literal": -1*next_arg["literal"],
                                "pos": arg["pos"]
                            }] + args[i+2:]
                        else:
                            args = args[0:i]+[{
                                "operator": arg["operator"],
                                "pos": arg["pos"],
                                "args": [next_arg]
                            }]+ args[i+2:]

            i -= 1


        # check that args are correctly formed, with operators in every second location, ie "e op e op e" and all operators
        # are binary operators with no arguments already assigned
        for i in range(len(args)):
            arg = args[i]
            if i % 2 == 1:
                if "operator" not in arg or "args" in arg:
                    raise ExpressionParser.ParseError("operator_expected",arg["pos"],"")
                else:
                    if arg.get("operator","") not in self.binary_operators:
                        raise ExpressionParser.ParseError("binary_operator_expected",arg["pos"])

            if i % 2 == 0 or i == len(args)-1:
                if arg.get("operator","") and "args" not in arg:
                    raise ExpressionParser.ParseError("operator_unexpected",arg["pos"],"")

        return self.refine_binary(args)

    def strip_debug(self,expr):
        if "pos" in expr:
            del expr["pos"]
        if "args" in expr:
            expr["args"] = [self.strip_debug(e) for e in expr["args"]]
        return expr

