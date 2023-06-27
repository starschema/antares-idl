#!/bin/bash

# The first argument is assigned to the variable 'input'
input=${LOAD_MODEL:-"predict"}

# Check the input value and execute the corresponding script
if [[ $input == "predict" ]]; then
    echo "Executing main_predict.py"
    python main_predict.py
elif [[ $input == "load" ]]; then
    echo "Executing main_data_load.py"
    python main_data_load.py
else
    echo "Invalid input. Please enter either 'load' or 'predict'."
fi
