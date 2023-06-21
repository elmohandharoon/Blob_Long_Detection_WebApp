# -*- coding: utf-8 -*-
"""Smell_Detection_Web_App.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1aKx6UwXOr5yoZJlpggJHPa7LHCEfWgCl
"""


#web app using flask and ngrok to run the app from google virsual machine

!pip install flask-ngrok
!pip install pyngrok
!pip install torch transformers
!pip install transformers
!pip install javalang
import nltk
import pandas as pd
import torch
import javalang
import numpy as np
import joblib
import ast
from transformers import BertModel
from transformers import BertTokenizer
from sklearn.preprocessing import StandardScaler
from javalang.ast import Node
from javalang.parser import Parser
from javalang.tokenizer import tokenize
from flask import Flask, render_template, request
from flask_ngrok import run_with_ngrok
from werkzeug.utils import secure_filename
from pyngrok import ngrok

app = Flask(__name__, template_folder='/content/templates')
#ngrok.set_auth_token('2RQiWOdFHplAaSpQUCH9WOV1auv_2ceqcvPyqL8Wz7uQPBWVN')
#run_with_ngrok(app)

#preprocess class snippets
#count_methods
def count_methods(code):
    # Tokenize and parse the evaluated code
    tokens = javalang.tokenizer.tokenize(code)
    parser = javalang.parser.Parser(tokens)
    tree = parser.parse_member_declaration()
    method_count = 0
    for path, node in tree:
        if isinstance(node, javalang.tree.MethodDeclaration):
            method_count += 1
    return method_count

#count_fields
def count_fields(code):
    # Tokenize and parse the evaluated code
    tokens = javalang.tokenizer.tokenize(code)
    parser = javalang.parser.Parser(tokens)
    tree = parser.parse_member_declaration()
    field_count = 0
    for path, node in tree:
        if isinstance(node, javalang.tree.FieldDeclaration):
            field_count += len(node.declarators)
    return field_count

def calculate_tcc(code):
    # Tokenize and parse the evaluated code
    tokens = javalang.tokenizer.tokenize(code)
    parser = javalang.parser.Parser(tokens)
    tree = parser.parse_member_declaration()

    method_pairs = 0
    common_method_pairs = 0

    for path, node in tree:
        if isinstance(node, javalang.tree.MethodDeclaration):
            method_pairs += 1
            method_invocations = set()
            for _, invocation_node in node.filter(javalang.tree.MethodInvocation):
                method_invocations.add(invocation_node.member)

            for _, other_node in tree:
                if isinstance(other_node, javalang.tree.MethodDeclaration):
                    if other_node.name != node.name:
                        other_method_invocations = set()
                        for _, invocation_node in other_node.filter(javalang.tree.MethodInvocation):
                            other_method_invocations.add(invocation_node.member)
                        if method_invocations.intersection(other_method_invocations):
                            common_method_pairs += 1

    if method_pairs > 0:
        tcc = common_method_pairs / method_pairs
    else:
        tcc = 0

    return tcc


def count_lines_of_code(code):
    # Split the code into lines
    lines = code.split('\n')

    # Count the non-empty lines of code
    loc = sum(1 for line in lines if line.strip() != '')

    return loc

def calculate_atfd(code):
    # Tokenize and parse the evaluated code
    tokens = javalang.tokenizer.tokenize(code)
    parser = javalang.parser.Parser(tokens)
    tree = parser.parse_member_declaration()

    atfd = 0  # Initialize the ATFD metric to 0

    field_declarations = set()  # Store the field declarations in the class

    for path, node in tree:
        if isinstance(node, javalang.tree.FieldDeclaration):
            # Add the field names to the set of field declarations
            for declarator in node.declarators:
                field_declarations.add(declarator.name)

        if isinstance(node, javalang.tree.MethodDeclaration):
            for parameter in node.parameters:
                # Check if the parameter type is from an unrelated class
                if parameter.type.name not in field_declarations:
                    atfd += 1  # Increment the ATFD metric

            if node.body is not None:
                for statement in node.body:
                    # Check if the statement is a method invocation
                    if isinstance(statement, javalang.tree.MethodInvocation):
                        # Check if the invoked method belongs to an unrelated class
                        if statement.member not in field_declarations:
                            atfd += 1  # Increment the ATFD metric

    return atfd



def calculate_cyclomatic_complexity(code):
    try:
        # Tokenize and parse the evaluated code
        tokens = javalang.tokenizer.tokenize(code)
        parser = javalang.parser.Parser(tokens)
        tree = parser.parse_member_declaration()

        # Count the number of decision points (branches and loops)
        complexity = 1  # Start with a complexity of 1 for the method itself
        for _, node in tree:
            if isinstance(node, javalang.tree.IfStatement):
                complexity += 1
            elif isinstance(node, javalang.tree.ForStatement):
                complexity += 1
            elif isinstance(node, javalang.tree.WhileStatement):
                complexity += 1
            elif isinstance(node, javalang.tree.DoStatement):
                complexity += 1
            elif isinstance(node, javalang.tree.SwitchStatement):
                complexity += len(node.cases)

        return complexity

    except (SyntaxError, ValueError) as e:
        print("Error evaluating code:")
        print(code)
        raise e


def calculate_lcom5(code):
    # Tokenize and parse the code snippet
    tokens = javalang.tokenizer.tokenize(code)
    parser = javalang.parser.Parser(tokens)
    tree = parser.parse_member_declaration()

    # Collect all the method names and instance variables
    methods = {}
    variables = set()
    for _, node in tree:
        if isinstance(node, javalang.tree.MethodDeclaration):
            methods[node.name] = set()
            for path, child_node in node:
                if isinstance(child_node, javalang.tree.VariableDeclarator):
                    variables.add(child_node.name)
                    methods[node.name].add(child_node.name)

    # Calculate the LCOM5 metric
    lcom5 = 0
    for method1, vars1 in methods.items():
        for method2, vars2 in methods.items():
            if method1 != method2:
                common_vars = vars1.intersection(vars2)
                if len(common_vars) == 0:
                    lcom5 += 1

    return lcom5




#preprocess methods snippets
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
method_model = BertModel.from_pretrained("bert-large-uncased")
method_model.to(device)
method_model.eval()


nltk.download('punkt')  # Download necessary resources
def tokenize_java_code(code):
    return nltk.word_tokenize(code)



tokenizer = BertTokenizer.from_pretrained("bert-large-uncased")
def prepare_input_tensors(tokenized_code):
    input_dict = tokenizer.encode_plus(tokenized_code, add_special_tokens=True, max_length=512, padding='max_length', truncation=True, return_tensors='pt')
    input_ids = input_dict['input_ids'].squeeze(0).cpu().numpy()  # Move to CPU and convert to NumPy
    attention_mask = input_dict['attention_mask'].squeeze(0).cpu().numpy()  # Move to CPU and convert to NumPy
    return input_ids, attention_mask


def extract_line_embeddings(input_ids, attention_mask):
    with torch.no_grad():
        input_ids = torch.tensor(input_ids).unsqueeze(0).to(device)  # Convert input_ids to a tensor
        attention_mask = torch.tensor(attention_mask).unsqueeze(0).to(device)  # Convert attention_mask to a tensor
        outputs = method_model(input_ids=input_ids, attention_mask=attention_mask)
        line_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()  # Move to CPU and convert to NumPy
    return line_embeddings



def get_method_start_end(method_node, tree):
    startpos = None
    endpos = None
    startline = None
    endline = None
    for path, node in tree:
        if startpos is not None and method_node not in path:
            endpos = node.position
            endline = node.position.line if node.position is not None else None
            break
        if startpos is None and node == method_node:
            startpos = node.position
            startline = node.position.line if node.position is not None else None
    return startpos, endpos, startline, endline

def get_method_text(startpos, endpos, startline, endline, last_endline_index, codelines):
    if startpos is None:
        return "", None, None, None
    else:
        startline_index = startline - 1
        endline_index = endline - 1 if endpos is not None else None

        # 1. check for and fetch annotations
        if last_endline_index is not None:
            for line in codelines[(last_endline_index + 1):(startline_index)]:
                if "@" in line:
                    startline_index = startline_index - 1
        meth_text = "<ST>".join(codelines[startline_index:endline_index])
        meth_text = meth_text[:meth_text.rfind("}") + 1]

        # 2. remove trailing rbrace for last methods & any external content/comments
        # if endpos is None and
        if not abs(meth_text.count("}") - meth_text.count("{")) == 0:
            # imbalanced braces
            brace_diff = abs(meth_text.count("}") - meth_text.count("{"))

            for _ in range(brace_diff):
                meth_text = meth_text[:meth_text.rfind("}")]
                meth_text = meth_text[:meth_text.rfind("}") + 1]

        meth_lines = meth_text.split("<ST>")
        meth_text = "".join(meth_lines)
        last_endline_index = startline_index + (len(meth_lines) - 1)

        return meth_text, (startline_index + 1), (last_endline_index + 1), last_endline_index

def process_file(file_path):
    with open(file_path, 'r') as r:
        codelines = r.readlines()
        code_text = ''.join(codelines)

    tree = javalang.parse.parse(code_text)
    methods = {}
    lex = None
    for _, method_node in tree.filter(javalang.tree.MethodDeclaration):
        startpos, endpos, startline, endline = get_method_start_end(method_node, tree)
        method_text, startline, endline, lex = get_method_text(startpos, endpos, startline, endline, lex, codelines)
        methods[method_node.name] = method_text

    # Create a new DataFrame to store the extracted methods
    methods_new_data = pd.DataFrame(columns=['method_name', 'method_code_snippet'])
    methods_new_data['method_name'] = list(methods.keys())
    methods_new_data['method_code_snippet'] = list(methods.values())

    return methods_new_data

def get_class_body(class_node, codelines):
    class_start = class_node.position.line - 1
    brace_count = 0

    for index in range(class_start, len(codelines)):
        line = codelines[index]
        brace_count += line.count('{')
        brace_count -= line.count('}')
        if brace_count == 0:
            class_end = index + 1
            break

    class_body = '\n'.join(codelines[class_start:class_end])
    return class_body.strip()

def god_process_file(file_path):
    with open(file_path, 'r') as r:
      codelines = r.readlines()
      code_text = ''.join(codelines)

    tree = javalang.parse.parse(code_text)
    classes = []

    for _, class_node in tree.filter(javalang.tree.ClassDeclaration):
      class_name = class_node.name
      class_body = get_class_body(class_node, codelines)
      classes.append({'class_name': class_name, 'class_code_snippet': class_body})

    classes_new_data = pd.DataFrame(classes)
    return classes_new_data



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        file.save(filename)

        # dealing with mehods

        methods_new_data = process_file(filename)
        # Load the saved model
        long_loaded_model = joblib.load('long_method_pretrained_xgb_model.pkl')
        # Prepare input tensors for new data
        methods_new_data['tokenized_code'] = methods_new_data['method_code_snippet'].apply(tokenize_java_code)
        methods_new_data['input_ids'], methods_new_data['attention_mask'] = zip(*methods_new_data['tokenized_code'].map(prepare_input_tensors))
        methods_new_data['line_embeddings'] = methods_new_data.apply(lambda row: extract_line_embeddings(row['input_ids'], row['attention_mask']), axis=1)
        X_new = np.stack(methods_new_data['line_embeddings'].values)
        X_new = X_new.reshape(X_new.shape[0], -1)
        # Load the scaler and transform the new data
        long_scaler = joblib.load('long_scaler.pkl')  # Replace 'scaler.pkl' with the filename of your saved scaler
        X_new = long_scaler.transform(X_new)
        predictions = long_loaded_model.predict(X_new)
        # Add the predictions to the DataFrame
        methods_new_data['prediction'] = predictions
        # Add a column indicating if the method is a long method or not
        methods_new_data['is_long_method'] = methods_new_data['prediction'].map({1: 'Long Method', 0: 'Not Long Method'})

        #dealing with classes
        classes_new_data = god_process_file(filename)
        classes_new_data['count_methods'] = classes_new_data['class_code_snippet'].apply(count_methods)
        classes_new_data['count_fields'] = classes_new_data['class_code_snippet'].apply(count_fields)
        classes_new_data['tcc'] = classes_new_data['class_code_snippet'].apply(calculate_tcc)
        classes_new_data['loc'] = classes_new_data['class_code_snippet'].apply(count_lines_of_code)
        classes_new_data['atfd'] = classes_new_data['class_code_snippet'].apply(calculate_atfd)
        classes_new_data['cyclomatic_complexity'] = classes_new_data['class_code_snippet'].apply(calculate_cyclomatic_complexity)
        classes_new_data['lcom5'] = classes_new_data['class_code_snippet'].apply(calculate_lcom5)
        god_loaded_model = joblib.load('god_class_metric_based_SVM_model.pkl')
        god_scaler = joblib.load('god_scaler.pkl')
        features = ['count_methods', 'count_fields','tcc','cyclomatic_complexity', 'loc','atfd', 'lcom5']
        X_new_data = god_scaler.transform(classes_new_data[features])
        y_pred = god_loaded_model.predict(X_new_data)
        classes_new_data['prediction'] = y_pred
        classes_new_data['is_god_class'] = classes_new_data['prediction'].map({1: 'God Class', 0: 'Not God Class'})

        return render_template('index.html', methods_result=methods_new_data.to_dict(orient='records'), classes_result=classes_new_data.to_dict(orient='records'))


    else:
        error = "No file selected."
        return render_template('index.html', error=error)

if __name__ == '__main__':
    app.run()
