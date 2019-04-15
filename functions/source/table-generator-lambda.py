#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# author: Santiago Cardenas <sancard@amazon.com>, <santiago.cardenas@outlook.com>
# author: Vinod Shukla <shukvino@amazon.com>

import json
import urllib.request
from urllib.parse import urlparse

from collections import OrderedDict
import boto3
import tabulate
from ruamel.yaml import YAML

def getTemplateText(file_url):
    try:
        if file_url.startswith('http') or file_url.startswith('file:/'):
            template_raw_data = urllib.request.urlopen(file_url).read().decode('utf-8')
        elif file_url.startswith('s3:/'):
            s3 = boto3.resource('s3')
            s3_parse = urlparse(file_url)
            bucket = s3_parse.netloc
            s3_key = s3_parse.path.lstrip('/')
            s3_obj = s3.Object(bucket, s3_key)
            template_raw_data = s3_obj.get()["Body"].read().decode('utf-8')
        else:
            with open(file_url, 'rU') as template:
                template_raw_data = template.read()
                template.close()
        return template_raw_data.strip()
    except:
        return "ERROR"


def hasInterface(template_data):
    return True if 'Parameters' in template_data.keys() and \
                   'Metadata' in template_data.keys() and \
                   'AWS::CloudFormation::Interface' in template_data['Metadata'].keys() \
        else False


def hasParameters(template_data):
    return True if 'Parameters' in template_data.keys() else False


def checkRequiredParam(parameter, template_data):
    return template_data['Parameters'][parameter]['Default'] \
        if 'Default' in template_data['Parameters'][parameter] \
        else '<span class="red">Requires input</span>'


def checkEmptyDescription(parameter, template_data):
    return template_data['Parameters'][parameter]['Description'] \
        if 'Description' in template_data['Parameters'][parameter] \
        else ''


def buildTable(parameters, template_data):
    table_data = []
    for parameter in sorted(parameters):
        parameter_details = OrderedDict()
        parameter_details['Parameter'] = parameter
        parameter_details['Default'] = checkRequiredParam(parameter, template_data)

        if parameter_details['Default'] == '':
            parameter_details['Default'] = u'—'

        parameter_details['Description'] = checkEmptyDescription(parameter, template_data)

        table_data.append(parameter_details)
    return tabulate.tabulate(table_data, headers="keys", tablefmt="html") + '<br/>'


def buildSimpleTable(template_data):
    parameters = template_data['Parameters']
    return buildTable(parameters, template_data)


def buildGroupedParameters(table_data, group_parameter, parameter_labels, parameters, template_data, col):
    parameter_details = OrderedDict()
    p_name = ""
    p_label = ""
    if group_parameter in parameter_labels.keys():
        if col == '4':
            p_label += parameter_labels[group_parameter]['default']
        else:
            p_name += '<span class="label-name">' + parameter_labels[group_parameter]['default'] + '</span><br/>'
    if group_parameter in parameters:
        if col == '4':
            p_name += group_parameter
            parameter_details['Parameter label'] = p_label
            parameter_details['Parameter Name'] = p_name
        else:
            p_name += '(' + group_parameter + ')'
            parameter_details['Parameter label (name)'] = p_name

        parameter_details['Default'] = checkRequiredParam(group_parameter, template_data)

        if parameter_details['Default'] == '':
            parameter_details['Default'] = u'—'

        parameter_details['Description'] = checkEmptyDescription(group_parameter, template_data)

        table_data.append(parameter_details)


def buildGroupedTable(template_data, col):
    interface = template_data['Metadata']['AWS::CloudFormation::Interface']
    parameter_groups = interface['ParameterGroups']
    parameter_labels = interface['ParameterLabels']
    parameters = template_data['Parameters']

    tables = ''

    params_in_groups = []
    for group in parameter_groups:
        table_data = []
        tables += '<span class="group-name"><h2>' + group['Label']['default'] + ':</h2></span>'
        params_in_groups.extend(group['Parameters'])
        for group_parameter in group['Parameters']:
            buildGroupedParameters(table_data, group_parameter, parameter_labels, parameters, template_data, col)

        tables += tabulate.tabulate(table_data, headers="keys", tablefmt="html") + '<br/>'

    # Parameters not grouped
    leftover_params = set(parameters) - set(params_in_groups)
    if len(leftover_params) > 0:
        tables += '<span class="group-name">Other Parameters:</span>'
        tables += buildTable(leftover_params, template_data)

    return tables

def htmlData(current_file, col):
    tables = ''
    html_prefix = u'<!DOCTYPE HTML><html lang="en-US"><head><meta charset="UTF-8">' + u' <link rel="stylesheet" href="https://s3.amazonaws.com/aws-cfn-samples/quickstart-cfn-param-table-generator/resources/styles.css">'
    html_doc_data = '</head><body>{}</body></html>'

    template_raw_data = getTemplateText(current_file)

    if template_raw_data == "ERROR":
        error_message = "Error occurred retrieving file {}. <br/> Please make sure it is a valid http(s) url or s3 uri." \
                        "<br/> The http(s) url must be publicly reachable." \
                        "<br/> For s3 uri, you must supply the bucket name as the TemplatesBucket parameter during deployment." \
                        "<br/> See Lambda CloudWatch logs for details.".format(current_file)
        return html_prefix + html_doc_data.format(error_message).replace("\n"," ")

    # print(template_raw_data)

    yaml = YAML()
    yaml.preserve_quotes = True
    template_data = yaml.load(template_raw_data)

    has_parameters = hasParameters(template_data)
    has_interface = hasInterface(template_data)

    if has_parameters:
        tables = tables + "<h1>" + current_file + "</h1>\n"

        if has_interface:
            tables += buildGroupedTable(template_data, col)
        else:
            print("No metadata section. That is no parameter groups and labels")
            tables += buildSimpleTable(template_data)

        tables += '<br/>'
    else:
        print("No parameters section in current file.")

    html_doc_data = html_doc_data.format(tables).replace("\n"," ")
    html_doc_data = html_prefix + html_doc_data

    return html_doc_data

# AWS Lambda handler
def lambda_handler(event, context):
    print("Event:")
    print(event)
    print("Url" + json.dumps(event['params']['querystring']))
    print("Url - Url: " + event['params']['querystring']['url'])
    current_file = event['params']['querystring']['url']
    col = event['params']['querystring'].get('col', '3')
    return htmlData(current_file, col)


# Script/Test harness
if __name__ == '__main__':
    # Absolute file path
    # result = htmlData('/tmp/test.yaml', 3)
    # File URL
    # result = htmlData('file:///tmp/test.json', '3')
    # S3 URL (Assumes authentication credentials provided via the default provider chain e.g. access keys, environment, role)
    # result = htmlData('s3://mybucket/test.template', 3)
    # HTTP URL (must be publicly reachable)
    result = htmlData('https://s3.amazonaws.com/aws-quickstart/quickstart-mongodb/templates/mongodb.template', 3)
    print(result)