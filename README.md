# DEPlot

DEPlot is an interactive visualization application for quantile evolution. It allows you to compare the errors of different models on time series data.

## Installation

### Prerequisites

- Python 3.x  
- pip (Python package installer)

### Installing Dependencies

You can install the required dependencies using the `requirements.txt` file:

```sh
pip install -r requirements.txt
```

## Usage

### Launching the Application

To start the application, run the `deplot.py` file:

```sh
python deplot.py
```

### Loading a CSV File

1. Click on `File` > `Open file`.
2. Select a CSV file containing model errors and various parameters in the following format:

    |  param1  |  param2  | target  | target_model1  | error_model1  | target_model2 | error_model2 |
    |----------|----------|---------|----------------|---------------|---------------|--------------|
    | value1_1 | value1_2 | target1 | target1_model1 | error1_model2 |      ...      |     ...      |
    | value2_1 | value2_2 | target2 | target2_model1 |      ...      |      ...      |     ...      |
    |   ...    |    ...   |   ...   |      ...       |      ...      |      ...      |     ...      |

    For example, for two models predicting house prices:

    |  rooms  |  size  | price  | price_model1 | error_model1 | price_model2 | error_model2 |
    |---------|--------|--------|--------------|--------------|--------------|--------------|
    |    4    |  120   | 154000 | 155400       |     1400     |   132600     |    -21400    |
    |    3    |   96   |  98450 |  98420       |      -30     |   109500     |     11050    |

    The file may optionally include a column grouping individuals and an index.
3. A preview window of the dataframe will appear. Select the appropriate settings (separator, index column, etc.).
4. Click `Confirm` to load the file.

### Model Selection

1. After the file is loaded, a model selection window will appear.
2. Select two models to compare by checking the corresponding boxes.
3. Click `OK` to display the graphs.

### Quantile Visualization

- Use the `Number of quantiles` slider to adjust the number of quantiles to visualize.
- To view the errors of a specific quantile, click on the boxplot associated with that quantile.

### Domain Evolution

- Select the `Convex Hull Percentage` to select the minimum percentage of points that the hull must contain.
- Use the `<target> range` to select the range of values to show in the plot.

### Managing Recent Files

- Recently opened files can be accessed via the `File` > `Recent files ►` menu.
- Opening parameters (separator, index column, selected models, etc.) are saved and automatically restored.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
