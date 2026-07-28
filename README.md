Basic MAT-4 Transpiler
======================

## MAT-4 Transpiler
A tiny and basic transpiler for the MAT-4 language. Transpiles MAT-4 code to C. I don't really have access to any MAT-4 manual, so this is in large based on my extrapolation of rules.

This is a very small project to experiment with this interesting language. It is intentionally simple, and probably won't get any updates.

The implementation is based on "Słownik instrukcji symbolicznych MAT-4" by Jaroslav Formandl and Jana Formandlowa, but I also recommend reading "Vademekum programisty MAT" by H. Radzikowski.

Additionally it only supports the Polish versions of commands.

This code is highly experimental, and I recommend to not imitate it.

## Goals
- Parse basic MAT-4 programs
- Generate functional C code
- Keep the implementation small

## Notable not implemented features
- Operations on perforated cards
- Operations on magnetic tapes
- Operations on absolute addresses
- `SPECJALNE`, `ADRES A DO B` and `ROZDZIAL` instructions
- Keys checking
- Functions are only supported as standalone statments e. g. `A = COS B`
- Printed numbers aren't always formatted exactly correctly

## Usage
```
$ python3 transpiler.py --help
usage: transpiler.py [-h] [-o output_file] [-es] input_filename

Transpile MAT-4 to C.

positional arguments:
  input_filename        name of the input file

options:
  -h, --help            show this help message and exit
  -o, --output output_file
                        specify the name of the output file
  -k40, --klucz-40      turn on printing variables from "PROBNE" instruction
  -m2, --m2-ccit        specify if IO commands use M2/CCIT encoding, defaults to ASCII
```
Notably, where in the primary source there's a "X" sign, it's replaced by "#" sign in this implementation.

Compatibility with older (e. g. Mińsk-22) programs may break due to integer sizes. This implementation assumes 64-bit long `long int`s.

The transpiled code works on ASCII by default instead of M2/CCIT, so it puts the characters in the last 7 bits, not 6.
