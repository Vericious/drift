"""Sample argparse CLI for testing the ArgparseExtractor."""
import argparse

parser = argparse.ArgumentParser(description="Sample CLI tool")
parser.add_argument('input_file', help='Input file path')
parser.add_argument('--output', '-o', type=str, default='out.txt', help='Output file')
parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
parser.add_argument('--format', choices=['json', 'csv', 'text'], default='text')
parser.add_argument('--count', type=int, required=True)
