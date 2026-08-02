def tokenise(target_string: str, operations_list: str, operations_dict: dict):
    tokens = []
    t = ""
    for i in target_string:
        if i in operations_list:
            if t != "": tokens.append(["VALUE", t])
            tokens.append([operations_dict[i], i])
            t = ""
        else:
            t += i
    if t != "": tokens.append(["VALUE", t])
    return tokens

def count_tokens(tokens) -> int:
    token_count = 0
    for i in tokens:
        if i[0] != "SPACE" and i[0] != "NEW_LINE":
            token_count += 1
        else:
            break
        #print(i)
    return token_count

def is_number(number: str) -> bool:
    try:
        number = float(number)
        return True
    except ValueError:
        return False

def convert(text: str) -> str:
    # T
    if len(text) == 1 and text.isalpha():
        return f"(*({text}))"
    letter = text[0]
    i = 1
    # Read first number
    number = ""
    while i < len(text) and text[i].isdigit():
        number += text[i]
        i += 1
    # B10
    if i == len(text):
        return f"(*({letter} + {number}))"
    # B11B10
    if text[i].isalpha() and "(" not in text:
        letter2 = text[i]
        i += 1
        number2 = ""
        while i < len(text) and text[i].isdigit():
            number2 += text[i]
            i += 1
        if number != "" and number2 != "":
            return f"(*({letter} + {number} + (int)*({letter2} + {number2})))"
        elif number == "" and number2 != "":
            return f"(*({letter} + (int)*({letter2} + {number2})))"
        elif number == "" and number2 == "":
            return f"(*({letter} + (int)*({letter2})))"
        elif number != "" and number2 == "":
            return f"(*({letter} + {number} + (int)*({letter2})))"

    # A2(...)
    if text[i] == "(":
        inner = convert_expression(text[i + 1:-1])
        if number:
            return f"(*({letter} + {number} + (int)({inner})))"
        return f"(*({letter} + (int)({inner})))"
    return text


def convert_expression(expr: str) -> str:
    i = 0
    def parse_ref():
        nonlocal i
        letter = expr[i]
        i += 1
        # Read digits
        digits = ""
        while i < len(expr) and expr[i].isdigit():
            digits += expr[i]
            i += 1
        base = letter
        if digits:
            base += "+" + digits
        # Adjacent reference?
        if i < len(expr) and expr[i].isalpha():
            rhs = parse_ref()
            return f"*({base} + {rhs})"
        return f"*({base})"
    out = ""
    while i < len(expr):
        c = expr[i]
        if c.isalpha():
            out += parse_ref()
        else:
            out += c
            i += 1
    return out

# This is the function that takes an expression and converts MAT variables, arrays and numbers into C's
# It tokenises it, then on each found individual values calls convert()
# Convert() calls convert_expression(), which calls an inner parse_ref()
def parse_expression(expression: str) -> str:
    if expression.startswith("#"):
        if is_number(expression[1:]):
            expression = expression.replace("#", "0")
        else:
            expression = parse_expression(expression[1:])
        return expression
    if "." in expression:
        expression = expression.replace(".", "*")
    if "," in expression:
        expression = expression.replace(",", ".")
    if is_number(expression):
        # Get rid of accidental octals
        while expression[0] == "0" and len(expression) > 1:
            expression = expression[1:]
        return expression

    operations_list = "()*/-+"
    operations_dict = {
        "(": "LEFT_P",
        ")": "RIGHT_P",
        "*": "MULTIPLY",
        "/": "DIVIDE",
        "-": "MINUS",
        "+": "PLUS"
        }
    tokenised_expression = tokenise(expression, operations_list, operations_dict)
    # In the tokenised expression find each value (B11B111, 45, G(5-JI))
    if len(tokenised_expression) == 1:
        expression = convert(expression)
        return expression
    expression = ""
    values = []
    operators = []
    count = 0
    for i in tokenised_expression:
        if i[0] == "LEFT_P":
            count += 1
            expression += i[1]
        elif i[0] == "RIGHT_P":
            count -= 1
            expression += i[1]
        elif i[0] != "VALUE" and count == 0:
            values.append(expression)
            operators.append(i[1])
            expression = ""
        else:
            expression += i[1]
    if expression != "": values.append(expression)
    expression = ""
    for i in values:
        if is_number(i):
            expression += i
        else:
            converted = convert(i)
            # Get rid of accidental octals
            while converted[0] == "0" and len(converted) > 1:
                converted = converted[1:]
            expression += converted
        if operators != []:
            expression += operators.pop(0)
    return expression

# Handle delarations:
# - CALKOWITE
# - RZECZYWISTE
# - FUNKCJE
# - ETYKIETY
# NOT START -> this declaration is handled directly in tokenise()
def declarations(declaration: str) -> str:
    if declaration[0][1][:4] == "FUNK":
        math = ["COS", "SIN", "ARCTG", "PWK", "LOG", "EXP", "EPWK"]
        function_names = [0]
        for i in declaration[2:]:
            if i[0] == "VALUE":
                function_names.append(i[1])
        if any(function in math for function in function_names):
            function_names[0] = "$$"
        return "", 0, -1, function_names
    if declaration[0][1][:4] == "ETYK":
        return "", 0, int(declaration[2][1]), [0]
    result = ""
    for i in declaration:
        result += i[1]
    var_type = "volatile "
    if result.startswith("CALK"):
        var_type += "long int"
    else:
        var_type += "double"
    change_index = 0
    array = result.split(" ")[1].split(":")
    result = ""
    for i in array:
        result += var_type + " "
        # Change arrays to C style
        if len(i)>1:
            result += i[0] + "[" + i[2:-1] + "+1]"
        else:
            result += i + "[1]"
        result += ";\n"
        change_index += 1
    return result, change_index, -1, [0]

# Handle arithmetic operations
# - A=B
# - A=B+C
# - A=B-C
# - A=B.C
# - A=B/C
def arithmetic(math_operation) -> str:
    result = ""
    for i in math_operation:
        result += i[1]
    result = result.split("=")
    result = parse_expression(result[0]) + "=" + parse_expression(result[1]) + ";\n"
    return result

# Handle functions:
# - SIN
# - COS
# - ARCTG
# - PWK
# - LOG
# - EXP
# - ENTIER
# - ULAMEK
# - ABS
# - EPWK
# - NORM
# - POZYCJA
# - WYCINEK
def functions(function, function_names) -> str:
    result = ""
    for i in function:
        result += i[1]
    result = result.split("=")
    variable = parse_expression(result[0])
    result = result[1].split(" ")
    if result[0] not in function_names:
        raise SyntaxError("Function not defined.")
    argument = result[1]
    result = result[0]
    if result == "SIN":
        argument = parse_expression(argument)
        result = f"{variable}=sin({argument});\n"
    elif result == "COS":
        argument = parse_expression(argument)
        result = f"{variable}=cos({argument});\n"
    elif result == "ARCTG":
        argument = parse_expression(argument)
        result = f"{variable}=atan({argument});\n"
    elif result == "PWK":
        argument = parse_expression(argument)
        result = f"{variable}=sqrt({argument});\n"
    elif result == "LOG":
        argument = parse_expression(argument)
        result = f"{variable}=log({argument});\n"
    elif result == "EXP":
        argument = parse_expression(argument)
        result = f"{variable}=exp({argument});\n"
    elif result == "ENTIER":
        argument = parse_expression(argument)
        result = f"{variable}=(long int)({argument});\n"
    elif result == "ULAMEK":
        argument = parse_expression(argument)
        result = f"{variable}=({argument}-(long int)({argument}));\n"
    elif result == "ABS":
        argument = parse_expression(argument)
        result = f"{variable}=absd({argument});\n"
    elif result == "EPWK":
        argument = parse_expression(argument)
        result = f"{variable}=(long int)(sqrt({argument}));\n"
    elif result == "NORM":
        argument = parse_expression(argument)
        result = f"{variable}=(double)({argument});\n"
    elif result == "POZYCJA":
        argument = argument.split(":")
        for z, i in enumerate(argument):
            argument[z] = parse_expression(i)
        if argument[1].startswith("*"): argument[1] = argument[1][1:]
        result  = f"for (int i=1; i < {argument[2]}; ++i) {{\n"
        result += f"if (*({argument[1]})+i == {argument[0]}) {{ {variable}=*({argument[1]}+i+1); }} }}\n"
    elif result == "WYCINEK":
        argument = argument.split(":")
        for z, i in enumerate(argument):
            argument[z] = parse_expression(i)
        result=f"{variable}=(long int)(({argument[0]} >> {argument[1]}) & ((1L << {argument[2]}) - 1));\n"
    else:
        raise SyntaxError("Unrecognised function")
    return result

# Handle basic instructions:
# - KONIUNKCJA
# - LEWO
# - PRAWO
# - ZAMIEN
# - STOP
def instructions(instruction) -> str:
    result = ""
    for i in instruction:
        result += i[1]
    if result.startswith("STOP"):
        # No accumulator changes, nor START button
        return "return 0;\n"
    if result.startswith("ZAMI"):
        result = result.split(" ")[1]
        result = result.split(":")
        result[0] = parse_expression(result[0]).replace("*", "", 1)
        result[1] = parse_expression(result[1]).replace("*", "", 1)
        result = f"swap({result[0]},{result[1]});\n"
        return result
    result = result.split("=")
    result[1] = result[1].split(":")
    operation = ("<<" * result[0].startswith("LEWO") + ">>" * result[0].startswith("PRAW")
                + "|" * result[0].startswith("KONI"))
    result[0] = result[0].split(" ")[1]
    result = (parse_expression(result[0]) + "=" + parse_expression(result[1][0])
              + operation + parse_expression(result[1][1]) + ";\n")
    return result

# Handle jumping instructions:
# - SKOCZ DO A
# - GDY A:B SKOCZ DO C:D:E
# - GDY A SKOCZ DO B:C:D
def jump_inst(instruction, label_number: int) -> str:
    result = ""
    if instruction[0][1][:4] == "SKOC":
        if len(instruction) < 5:
            return ""
        result = instruction[4][1]
        if result == "0":
            return ""
        elif is_number(result):
            result = f"goto _{result};\n"
        else:
            result = parse_expression(result)
            result = f"switch ({result}) {{"
            for i in range(1, label_number):
                result += f" case {i}: goto _{i}; "
            result += "}\n"
        return result
    result = ""
    for i in instruction:
        result += i[1]
    result = result.split(" ")
    result = result[1:]
    # Check if A or A:B
    labels = []
    comparison = []
    if ":" in result[0]:
        result[0] = result[0].split(":")
        index: int = 0
        if len(result) == 4:
            index = 3
        elif len(result) == 3:
            index = 2
        elif len(result) == 2:
            index = 1
        else:
            raise SyntaxError("Improperly constructed GDY statement.")
        comparison = [parse_expression(result[0][0]), parse_expression(result[0][1])]
    else:
        index: int = 0
        if len(result) == 4:
            index = 3
        elif len(result) == 3:
            index = 2
        elif len(result) == 2:
            index = 1
        else:
            raise SyntaxError("Improperly constructed GDY statement.")
        comparison = [parse_expression(result[0]), "0"]
    result[index] = result[index].split(":")
    for i in result[index]:
        labels.append(i)
    if index == 2:
        labels = labels[1:] + ["0"]
    elif index == 1:
        labels = labels[2:] + ["0", "0"]
    #print(comparison, labels)
    a, b = comparison
    result = f"""if ({a}<{b}) {{
    {'// ' if labels[0] == '0' else ''}goto _{labels[0]};
}} else if ({a}=={b}) {{
    {'// ' if labels[1] == '0' else ''}goto _{labels[1]};
}} else if ({a}>{b}) {{
    {'// ' if labels[2] == '0' else ''}goto _{labels[2]};
}}\n"""
    return result

# Handle subroutine instructions:
# - PODPROGRAM
# - WROC
def subroutine_inst(instruction, label_number: int = -1) -> str:
    if instruction[0][1] == "WROC":
        return "longjmp(podpr_env, 1);\n"
    result = instruction[2][1]
    if is_number(result):
        return "if (setjmp(podpr_env) == 0) { goto _"+result+"; }\n"
    elif label_number == -1:
        return "//if (setjmp(podpr_env) == 0) { goto "+result+"; }\n"
    # Label number is known, and we jump to a variable
    result = parse_expression(result)
    result = f"if (setjmp(podpr_env) == 0) {{ switch ({result}) {{"
    for i in range(1, label_number):
        result += f" case {i}: goto _{i}; "
    result += "} }\n"
    return result

# Handle loop instructions:
# - DLA A=B:C:.D
# - DLA A=B:C:=D
# - DLA A=B:C:(D
# - DLA A=V:V:)D
# - POWTORZ A
def loop_inst(instruction, loop_labels, label_number: int = -1) -> str:
    if instruction[0][1][:4] == "POWT":
        label, variable, loop_step, loop_comparison, loop_end = loop_labels[-1]
        label_number = label[4:]
        if loop_comparison == ".":
            result = f"if (loop{label_number} != {loop_end}) {{\n"
            result +=f"{variable} = {variable} + ({loop_step});\n"
            result +=f"++loop{label_number};\n"
            result +=f"goto {label}; }}\n"
        elif loop_comparison == "(" or loop_comparison == ")":
            if loop_comparison == "(": loop_comparison = ">="
            if loop_comparison == ")": loop_comparison = "<="
            result = f"if ({variable} {loop_comparison} {loop_end}) {{\n"
            result +=f"{variable} = {variable} + ({loop_step});\n"
            result +=f"goto {label}; }}\n"
        elif loop_comparison == "=":
            result = f"if (loop_check({variable},{loop_end},{loop_step})) {{\n"
            result +=f"{variable} = {variable} + ({loop_step});\n"
            result +=f"goto {label}; }}\n"
        else:
            raise SyntaxError("Incorrect loop syntax")
        return result, ""
    label = [f"LOOP{label_number}"]
    instruction = instruction[2:]
    result = ""
    for i in instruction:
        result += i[1]
    result = result.split("=", 1)
    variable: str = parse_expression(result[0])
    result = result[1].split(":")
    loop_start: str = parse_expression(result[0])
    loop_step: str = parse_expression(result[1])
    loop_comparison: str = result[2][0]
    loop_end: str = parse_expression(result[2][1:])
    #print(label, variable, loop_start, loop_step, loop_comparison, loop_end)
    label = label + [variable, loop_step, loop_comparison, loop_end]
    result = f"{variable}={loop_start};\n"
    if loop_comparison == ".":
        result += f"int loop{label_number} = 1;\n"
    result += f"{label[0]}: ;\n"
    return result, label

# Handle instructions reading input:
# - WEJSCIE  (Ignored)
# - CZLICZBE
# - CZLICZBE A'B'C
# - CZSYMBOL
# - CZTEKST
# - CZTEKST A:B:C:D:E:F
def read_inst(instruction, use_encoding: bool = False) -> str:
    result = instruction[0][1][:4]
    if result == "WEJS": return ""
    elif result == "CZLI":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        if "'" in result:
            variable = result.split("'")
            result = ""
            for i in variable:
                i = parse_expression(i)
                result  += "{ double placeholder;\n"
                result  += "scanf(\"%lf\", &placeholder);\n"
                result += f"{i} = placeholder; }}\n"
        else:
            variable = parse_expression(result)
            result   = "{ double placeholder;\n"
            result  += "scanf(\"%lf\", &placeholder);\n"
            result += f"{variable} = placeholder; }}\n"
    elif result == "CZSY":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        variable = parse_expression(result)
        result = "{ int ch = getchar();\n"
        if not use_encoding:
            result += f"if (ch != EOF) {{ {variable} = ({variable} & ~0177) | (ch & 0177); }} }}\n"
        else:
            result +=  "if (ch != EOF) {\n"
            result +=  "ch = encode[(unsigned char)ch][0];\n"
            result += f"{variable} = ({variable} & ~077) | (ch & 077); }} }}\n"
    elif result == "CZTE":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        variable = ["022"]
        variable_change = 0
        if ":" in result:
            result = result.split(":")
            variable = []
            variable_change = 1
            for i in result[1:]:
                variable.append(parse_expression(i))
            result = result[0]
        main_variable = parse_expression(result)[2:-1]
        condition = f"((ch == {variable[0]})"
        for i in variable[1:]:
            condition += f" || (ch == {i})"
        condition += ")"
        result = ""
        if use_encoding:
            result +=  "{\n"
            result += f"long int* ptr = {main_variable};\n"
            result +=  "char opcode = 1;\n"
            result +=  "while (opcode) {\n"
            result +=  "int ch = getchar();\n"
            result +=  "if (ch == EOF) { break; }\n"
            result +=  "ch = encode[(unsigned char)ch][0];\n"
            result += f"if {condition} {{ break; }}\n"
            result +=  "*(ptr) &= ((1L << 36) - 1);\n"
            result +=  "*(ptr) &= ~(((1L << 6) - 1) << (6*5));\n"
            result +=  "*ptr |= ((long int)ch << (5 * 6));\n"
            result +=  "for (int i = 0; i < 5; i++) {\n"
            result +=  "    int ch = getchar();\n"
            result +=  "    if (ch == EOF) { opcode = 0; break; }\n"
            result +=  "    ch = encode[(unsigned char)ch][0];\n"
            result += f"    if {condition} {{ opcode = 0; break; }}\n"
            result +=  "    *(ptr) &= ~(((1L << 6) - 1) << (6*(4-i)));\n"
            result +=  "    *ptr |= ((long int)ch << ((4-i) * 6));\n"
            result +=  "}\n"
            result +=  "ptr = ptr + 1;\n"
            result +=  "}}\n"
        else:
            if (condition == "((ch == 022))" and not variable_change):
                condition = "(ch == 052)"
            result +=  "{\n"
            result += f"long int* ptr = {main_variable};\n"
            result +=  "char opcode = 1;\n"
            result +=  "while (opcode) {\n"
            result +=  "int ch = getchar();\n"
            result +=  "if (ch == EOF) { break; }\n"
            result += f"if {condition} {{ break; }}\n"
            result +=  "*(ptr) &= ((1L << 42) - 1);\n"
            result +=  "*(ptr) &= ~(((1L << 7) - 1) << (7*5));\n"
            result +=  "*ptr |= ((long int)ch << (5 * 7));\n"
            result +=  "for (int i = 0; i < 5; i++) {\n"
            result +=  "    int ch = getchar();\n"
            result +=  "    if (ch == EOF) { opcode = 0; break; }\n"
            result += f"    if {condition} {{ opcode = 0; break; }}\n"
            result +=  "    *(ptr) &= ~(((1L << 7) - 1) << (7*(4-i)));\n"
            result +=  "    *ptr |= ((long int)ch << ((4-i) * 7));\n"
            result +=  "}\n"
            result +=  "ptr = ptr + 1;\n"
            result +=  "}}\n"
    return result

# Handle printing instructions:
# - WYJSCIE  (Ignored)
# - DRLICZBE A
# - DRLICZBE A'B'C
# - DRLICZBE A,B
# - DRLICZBE A,B/
# - DRLICZBE A,B:C
# - DRSYMBOL A
# - DRTEKST A
# - SPACJA
# - LINIA
# - NAPIS
# - STRONA (Different behaviour, prints page break)
def write_inst(instruction, use_encoding: bool = False) -> str:
    result = instruction[0][1][:4]
    if result == "WYJS": return ""
    elif result == "LINI" or result == "SPAC":
        number = "1"
        if len(instruction) > 2:
            number = ""
            for i in instruction[2:]:
                number += i[1]
            number = parse_expression(number)
        symbol = "\\n"*(result == "LINI") + " "*(result == "SPAC")
        result = f"for (int i=0; i<{number}; ++i) {{ putchar('{symbol}'); }}\n"
    elif result == "STRO":
        if len(instruction) > 2:
            result = r"\f"
            result = f"putchar('{result}');\n"
        else:
            result = ""
    elif result == "NAPI":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        result = result[:-2]
        result = f"printf(\"{result}\");\n"
    elif result == "DRLI":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        if "," in result and "/" in result:
            result = result.split(",")
            result[0] = parse_expression(result[0])
            result[1] = parse_expression(result[1][:1])
            result = f"printf(\"%.*E\", {result[1]} - 1, {result[0]});\n"
        elif "," in result and ":" in result:
            result = result.split(",")
            result[0] = parse_expression(result[0])
            result[1] = result[1].split(":")
            a = result[0]
            b = parse_expression(result[1][0])
            c = parse_expression(result[1][1])
            result = f"printf(\"%0*.*f\", ({b}) + ({c}) + 1, ({c}), (double){a});\n"
        elif "," in result:
            result = result.split(",")
            result[0] = parse_expression(result[0])
            result[1] = parse_expression(result[1])
            result = f"print_width({result[0]}, {result[1]});\n"
        elif "'" in result:
            numbers = result.split("'")
            result = ""
            for i in numbers:
                i = parse_expression(i)
                result += f"print_number({i});\n"
        else:
            result = parse_expression(result)
            result = f"print_number({result});\n"
    elif result == "DRSY":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        result = parse_expression(result)
        if use_encoding:
            result = f"putchar(decode[{result} & 077]);\n"
        else:
            result = f"putchar({result} & 0177);\n"
    else:
        variable = ""
        for i in instruction[2:]:
            variable += i[1]
        variable = parse_expression(variable)[2:-1]
        encodings = []
        encodings += ((["((*ptr >> ((5-i) * 7)) & 0177)", "ch", "055"] * (not use_encoding))
                      + (["((*ptr >> ((5-i) * 6)) & 077)", "decode[ch]", "030"] * use_encoding))
        result  =  "{\n"
        result += f"long int* ptr = {variable};\n"
        result +=  "char opcode = 1;\n"
        result +=  "while (opcode) {\n"
        result +=  "for (int i = 0; i < 6; i++) {\n"
        result += f"    int ch = {encodings[0]};\n"
        result += f"    putchar({encodings[1]});\n"
        result += f"    if (ch == {encodings[2]}) {{ opcode = 0; break; }}\n"
        result +=  "}\n"
        result +=  "ptr = ptr + 1;\n"
        result +=  "}}\n"
    return result

# Handle different printing instructions:
# - WYPISZ
# - WYSUW
# - PROBNE
def write2_inst(instruction, klucz_40: bool = False) -> str:
    if instruction[0][1][:4] == "PROB" and klucz_40:
        result = ""
        for i in instruction[2:]:
            result += i[1]
        result = parse_expression(result)
        return f"print_number({result});\n"
    elif instruction[0][1][:4] == "WYSU":
        return "printf(\"\\n\");\n"
    elif instruction[0][1][:4] == "WYPI":
        result = ""
        for i in instruction[2:]:
            result += i[1]
        result = parse_expression(result)
        return f"print_number({result});\n"
    return ""

# Handle final instructions:
# NOT SPECJALNE    |
# NOT ADRES A DO B | -> it's out of scope for this project
# NOT ROZDZIAL A   |
# - WARTOSC A(B:C)=D:E:F:G
# - WARTOSC A=B
def final_inst(instruction) -> str:
    #print(instruction)
    result = ""
    if ["COLON", ":"] in instruction:
        line = ""
        for i in instruction[2:]:
            line += i[1]
        eq = line.index('=')
        left = line[:eq]
        values = line[eq + 1:].split(':')
        lpar = left.index('(')
        colon = left.index(':')
        rpar = left.index(')')
        name = left[:lpar]
        start = int(left[lpar + 1:colon])
        end = int(left[colon + 1:rpar])
        assignments = []
        for index in range(start, end + 1):
            assignments.append(f"{name}[{index}] = {values[index - start]};")
        result = " ".join(assignments) + "\n"
    else:
        instruction = instruction[2:]
        for i in instruction:
            result += i[1]
        result = result.split("=")
        result = parse_expression(result[0]) + "=" + parse_expression(result[1]) + ";\n"
    return result, 1

# Tokenises each line, splits it apart and distributes the parts to corresponding functions
# Then compiles the results together and puts them into the output file
def transpile(input_file, output_file, klucz_40, use_encoding):
    # Some variable declarations
    operations_list = "()./-+,:'#= \n"
    operations_dict = {
        "(": "LEFT_P",
        ")": "RIGHT_P",
        ":": "COLON",
        "'": "APOST",
        "#": "KRATKA",
        ".": "MULTIPLY",
        "/": "DIVIDE",
        "-": "MINUS",
        "+": "PLUS",
        ",": "COMMA",
        " ": "SPACE",
        "=": "EQUAL",
        "\n": "NEW_LINE"
        }
    function_names = []
    loop_labels = []
    loop_label = []
    loop_label_number: int = 0
    end_of_variables: int = 0
    last_wart = False
    label_number: int = -1
    include_math: int = 0
    # Initialise some default stuff
    current_index: int = 0
    # Libraries for io and jumps
    output_file.writelines("#include <stdio.h>\n")
    output_file.writelines("#include <setjmp.h>\n")
    # Set the jump variable
    output_file.writelines("jmp_buf podpr_env;\n")
    # Swap functions for ZAMIEN
    output_file.writelines("void swap_int(long int *a, long int *b) { long int temp = *a; *a = *b; *b = temp; }\n")
    output_file.writelines("void swap_double(double *a, double *b) { double temp = *a; *a = *b; *b = temp; }\n")
    output_file.writelines("#define swap(a, b) _Generic((a), long int *: swap_int, double *: swap_double )(a, b)\n")
    # ABS function and loop condition checking
    output_file.writelines("double absd(double x) { return (x < 0.0f) ? -x : x; }\n")
    output_file.writelines("int check_int(long int a, long int d, long int c) { (void)c; return a != d; }\n")
    output_file.writelines("int check_double(double a, double d, double c) { return absd(d - a) >= absd(c / 2.0); }\n")
    output_file.writelines("#define loop_check(a, d, c) _Generic((a), long int: check_int, double: check_double)(a, d, c)\n")
    # Output functions
    output_file.writelines("void print_int(long int x) { printf(\"%ld\", x); }\n")
    output_file.writelines("void print_double(double x) { printf(\"%f\", x); }\n")
    output_file.writelines("#define print_number(x) _Generic((x), long int: print_int, double: print_double)(x)\n")
    output_file.writelines("void print_int_width(long int value, int width) { printf(\"%*ld\", width, value); }\n")
    output_file.writelines("void print_double_width(double value, int width) { printf(\"%*f\", width, value); }\n")
    output_file.writelines("#define print_width(value, width) _Generic((value), long int: print_int_width, double: print_double_width )(value, width)\n")
    # Encoding
    # I used $ for NUMBERS and @ for LETTERS
    output_file.writelines("const unsigned char encode[128][2] = {[0] = {0, 32}, [10] = {8, 40}, [13] = {2, 34}, [32] = {4, 36}, [35] = {19, 255}, [36] = {27, 59}, [37] = {5, 255}, [40] = {30, 255}, [41] = {9, 255}, [42] = {18, 255}, [43] = {17, 255}, [44] = {6, 255}, [45] = {24, 255}, [46] = {7, 255}, [47] = {23, 255}, [48] = {13, 35}, [49] = {29, 255}, [50] = {25, 255}, [51] = {16, 255}, [52] = {10, 255}, [53] = {1, 255}, [54] = {21, 255}, [55] = {28, 60}, [56] = {12, 255}, [57] = {3, 255}, [58] = {14, 255}, [59] = {26, 255}, [61] = {15, 255}, [62] = {20, 255}, [64] = {31, 63}, [65] = {56, 255}, [66] = {50, 255}, [67] = {46, 255}, [68] = {51, 255}, [69] = {48, 255}, [70] = {54, 255}, [71] = {43, 255}, [72] = {37, 255}, [73] = {44, 255}, [74] = {58, 255}, [75] = {62, 255}, [76] = {41, 255}, [77] = {39, 255}, [78] = {38, 255}, [80] = {45, 255}, [81] = {61, 255}, [82] = {42, 255}, [83] = {52, 255}, [84] = {33, 255}, [86] = {47, 255}, [87] = {57, 255}, [88] = {55, 255}, [89] = {53, 255}, [90] = {49, 255}, [91] = {22, 255}, [93] = {11, 255}};\n"
                           * use_encoding)
    output_file.writelines("const char decode[64] = {'\\0', '5', '\\r', '9', ' ', '%', ',', '.', '\\n', ')', '4', ']', '8', '0', ':', '=', '3', '+', '*', '#', '>', '6', '[', '/', '-', '2', ';', '$', '7', '1', '(', '@', '\\0', 'T', '\\r', '0', ' ', 'H', 'N', 'M', '\\n', 'L', 'R', 'G', 'I', 'P', 'C', 'V', 'E', 'Z', 'B', 'D', 'S', 'Y', 'F', 'X', 'A', 'W', 'J', '$', '7', 'Q', 'K', '@' };\n"
                           * use_encoding)
    current_index += 2 * use_encoding
    # int main()
    output_file.writelines("int main() {\n")
    current_index += 17
    for line in input_file:
        # Tokenise each line
        tokens = tokenise(line, operations_list, operations_dict)
        #print(tokens)
        # Get rid of preceding spaces
        while tokens[0][0] == "SPACE":
            tokens = tokens[1:]
        # Ignore comments
        if tokens[0][0] == "COLON": continue
        # Ignore empty lines
        if tokens[0][0] == "NEW_LINE": continue
        if tokens[0][0] != "VALUE":
            raise SyntaxError("Unexpected token")
        empty_pass: bool = False
        token_count: int = 0
        change_index: int = 0
        result: str = ""
        while (tokens != [] and tokens[0][0] != "NEW_LINE"):
            # Handle preceding spaces
            if tokens[0][0] == "SPACE":
                tokens = tokens[1:]
                continue
            # Handle comments
            if tokens[0][0] == "COLON":
                break
            # Handle unrecognised directives
            if empty_pass:
                output_file.writelines(f"/*{tokens}*/\n")
                current_index += 1
                break
            # Handle "WARTOSC" instructions
            if tokens[0][1][:4] == "WART":
                last_wart = True
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result, change_index = final_inst(tokens[:token_count])
                output_file.writelines(result)
                current_index += change_index
                tokens = tokens[token_count:]
                continue
            if last_wart == True:
                end_of_variables = current_index
                last_wart = False
            # Handle labels
            if tokens[0][1].isdigit() and tokens[1][0] == "RIGHT_P":
                output_file.writelines(f"_{tokens[0][1]}: ;\n")
                current_index += 1
                tokens = tokens[2:]
                continue
            # Handle "START"
            if tokens[0][1] == "START":
                result = tokens[2][1]
                result = f"goto _{result};\n"
                output_file.writelines("}\n")
                return result, end_of_variables, include_math
            # Handle "CALKOWITE", "RZECZYWISTE", "FUNKCJE" and "ETYKIETY"
            if (tokens[0][1][:4] == "CALK" or tokens[0][1][:4] == "RZEC"
                or tokens[0][1][:4] == "FUNK" or tokens[0][1][:4] == "ETYK"):
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result, change_index, label_number, func = declarations(tokens[:token_count])
                include_math += int(func[0] == "$$" * (1-include_math))
                function_names = function_names + func[1:]
                output_file.writelines(result)
                current_index += change_index
                tokens = tokens[token_count:]
                continue
            # Handle general instructions without "STOP"
            if (tokens[0][1][:4] == "KONI" or tokens[0][1] == "LEWO"
                or tokens[0][1][:4] == "PRAW" or tokens[0][1][:4] == "ZAMI"):
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result = instructions(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle "STOP"
            if tokens[0][1] == "STOP":
                if len(tokens) >= 3:
                    # STOP A
                    token_count = 2
                    token_count += count_tokens(tokens[token_count:])
                else:
                    # just STOP
                    token_count = 1
                result = instructions(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle jumping instructions
            if tokens[0][1][:4] == "SKOC":
                token_count = 5
                result = jump_inst(tokens[:token_count], label_number)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if tokens[0][1] == "GDY":
                token_count = 0
                for z, i in enumerate(tokens):
                    if i[0] == "SPACE" and z > 1:
                        if tokens[z-1][0] == "SPACE":
                            break
                    elif i[0] == "NEW_LINE":
                        break
                    token_count += 1
                #print(token_count, tokens[:token_count])
                result = jump_inst(tokens[:token_count], label_number)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle subroutine instructions
            if tokens[0][1][:4] == "PODP":
                token_count = 3
                result = subroutine_inst(tokens[:token_count], label_number)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if tokens[0][1] == "WROC":
                token_count = 1
                result = subroutine_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle loop instructions
            if tokens[0][1] == "DLA":
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result, loop_label = loop_inst(tokens[:token_count], loop_labels, loop_label_number)
                loop_label_number += 1
                loop_labels.append(loop_label)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if tokens[0][1][:4] == "POWT":
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result, loop_label = loop_inst(tokens[:token_count], loop_labels)
                loop_labels = loop_labels[:-1]
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle input instructions
            if (tokens[0][1][:4] == "WEJS"):
                token_count = 3
                result = read_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if (tokens[0][1][:4] == "CZLI" or tokens[0][1][:4] == "CZTE"
                or tokens[0][1][:4] == "CZSY"):
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result = read_inst(tokens[:token_count], use_encoding)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle output instructions
            if tokens[0][1][:4] == "WYJS":
                token_count = 3
                result = write_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if (tokens[0][1][:4] == "DRLI" or tokens[0][1][:4] == "DRTE"
                or tokens[0][1][:4] == "DRSY"):
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result = write_inst(tokens[:token_count], use_encoding)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if (tokens[0][1][:4] == "NAPI"):
                token_count = 2
                for i in tokens[token_count:]:
                    token_count += 1
                    if i[0] == "KRATKA":
                        break
                result = write_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if (tokens[0][1][:4] == "STRO" or tokens[0][1][:4] == "SPAC"
                or tokens[0][1][:4] == "LINI"):
                if len(tokens) >= 3:
                    # STRONA/LINIA/SPACJA A
                    token_count = 2
                    token_count += count_tokens(tokens[token_count:])
                else:
                    # just STRONA/LINIA/SPACJA
                    token_count = 1
                result = write_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle different output instructions
            if tokens[0][1][:4] == "WYPI":
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result = write2_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if tokens[0][1][:4] == "WYSU":
                if len(tokens) > 3:
                    token_count = 2
                    token_count += count_tokens(tokens[token_count:])
                else:
                    token_count = 1
                result = write2_inst(tokens[:token_count])
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            if tokens[0][1][:4] == "PROB":
                token_count = 2
                token_count += count_tokens(tokens[token_count:])
                result = write2_inst(tokens[:token_count], klucz_40)
                output_file.writelines(result)
                tokens = tokens[token_count:]
                continue
            # Handle instructions with equal sign
            # Check if equal is in tokens
            if ["EQUAL", "="] in tokens:
                t1: int = next(
                    (i for i, token in enumerate(tokens) if token[0] == "EQUAL"),
                    len(tokens)
                )
                t2: bool = any(
                    token[0] == "COLON"
                    for token in tokens[:t1]
                )
                t1 = -2
                if not t2:
                    #print(tokens)
                    token_count = 2
                    token_count += count_tokens(tokens[token_count:])
                    for i in tokens[:token_count]:
                        if i[1] in function_names:
                            t1 = -1
                            break
                    if t1 == -2:
                        # Handle math without functions
                        result = arithmetic(tokens[:token_count])
                    else:
                        # Handle math with functions
                        for z, i in enumerate(tokens[token_count:]):
                            if (i[0] == "SPACE" and tokens[z-1][0] == "SPACE") or i[0] == "NEW_LINE":
                                break
                            token_count += 1
                        result = functions(tokens[:token_count], function_names)
                    output_file.writelines(result)
                    tokens = tokens[token_count:]
                    continue

            empty_pass = True

    return "", -1

def insert_START(first_label: str, end_of_variables: int, include_math: int, output_file):
    lines = output_file.readlines()
    lines.insert(end_of_variables, first_label)
    if include_math:
        lines.insert(0, "#include <math.h>\n")
        print("WARNING! Includes math.h")
    output_file.seek(0)
    output_file.writelines(lines)
    return

def main() -> int:
    # Import some libraries
    import os
    import sys
    import argparse

    # Create an argument parser
    parser = argparse.ArgumentParser(description="Transpile MAT-4 to C.")
    parser.add_argument('input_filename',
            help='name of the input file')
    parser.add_argument('-o', '--output', metavar='output_file', default='',
            help='specify the name of the output file')
    parser.add_argument('-k40', '--klucz-40', action='store_true',
            help='turn on printing variables from "PROBNE" instruction', default=True)
    parser.add_argument('-m2', '--m2-ccit', action='store_true',
            help='specify if IO commands use M2/CCIT encoding, defaults to ASCII', default=False)
    #parser.add_argument('-cm', '--compatibility-mode', action='store_true',
    #        help='turn on compatibility mode that tries to mimic Mińsk-22 machines', default=False)

    # Parse the command-line arguments
    args = parser.parse_args()
    input_filename = args.input_filename
    output_filename = args.output
    klucz_40 = args.klucz_40
    encoding = args.m2_ccit
    #compatibiliy = args.compatiblity_mode

    if not os.path.isfile(input_filename):
        print(f"{input_filename}: cannot open '{input_filename}': No such file or directory")
        sys.exit(1)

    # Create the output filename
    if output_filename == "":
        output_filename = os.path.splitext(input_filename)[0] + ".c"

    try:
        # Create the output file
        tmp = open(output_filename, 'w')
        tmp.close()

        # Transpile the code
        with open(input_filename, 'r') as input_file, open(output_filename, 'r+') as output_file:
            output_file.truncate()
            first_label, end_of_variables, include_math = transpile(input_file, output_file, klucz_40, encoding)
            if first_label == "" and end_of_variables == "-1":
                raise SyntaxError("START not declared")

        with open(output_filename, "r+") as output_file:
            insert_START(first_label, end_of_variables, include_math, output_file)

    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

    return 0

if __name__ == "__main__":
    main()
