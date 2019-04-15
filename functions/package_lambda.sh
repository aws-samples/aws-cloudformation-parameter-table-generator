#! /bin/bash

src_file=table-generator-lambda

rm -rf packages/*

cd packages
pip3 install ruamel.yaml --target .
pip3 install tabulate --target .
cp ../source/${src_file}.py .
zip -r --exclude=*.pyc --exclude=*.so ../cfn-${src_file}.zip .
cd ..
rm -rf packages/*
mv cfn-${src_file}.zip packages/
