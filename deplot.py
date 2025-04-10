import json
import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backend_bases import MouseEvent
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter.ttk import Treeview
import customtkinter as ctk
import numpy as np
from scipy.spatial.distance import mahalanobis
from widgets import CTkRangeSlider, IntSpinbox, NavToolbar
from tkcalendar import Calendar
from tkinter import Menu
from scipy.spatial import ConvexHull
# from depth.multivariate.Halfspace import halfspace

# Set the seaborn theme
# sns.set_theme()

def tukey_depth(points, query_point):
    """
    Calcule la profondeur de Tukey d'un point de requête par rapport à un ensemble de points.
    
    :param points: Un tableau numpy de forme (n, d) où n est le nombre de points et d est la dimension.
    :param query_point: Un tableau numpy de forme (d,) représentant le point de requête.
    :return: La profondeur de Tukey du point de requête.
    """
    n, d = points.shape
    depths = []

    for i in range(n):
        direction = points[i] - query_point
        if np.all(direction == 0):
            continue
        direction = direction / np.linalg.norm(direction)
        projections = np.dot(points - query_point, direction)
        depth = np.sum(projections >= 0) / n
        depths.append(depth)

    return min(depths)

class QuantileApp(ctk.CTk):
    """Main application class for the Quantile Evolution Plot."""
    def __init__(self):
        super().__init__()

        self.title("DEPlot")
        self.iconbitmap('deplot.ico')
        ctk.set_default_color_theme("blue")
        ctk.set_appearance_mode("dark")
        self.geometry("1600x800")
        # self.after(0, lambda: self.state('zoomed'))

        if os.name == 'nt':
            self.recent_files_path = os.path.join(os.getenv('APPDATA'), 'DEPlot', 'recent_files.json')
        else:
            self.recent_files_path = os.path.join(os.path.expanduser('~'), '.DEPlot', 'recent_files.json')
        self.recent_files = []

        self.menubar = tk.Menu(self)
        file_menu = tk.Menu(self.menubar, tearoff=0)
        
        self.menubar.add_cascade(label="File", menu=file_menu)

        file_menu.add_command(label="Open file", command=self.open_file)

        self.recent_files_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label='Recent files', menu=self.recent_files_menu)
        file_menu.add_command(label="Exit", command=self.quit)

        self.config(menu=self.menubar)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.is_simulating = False

        self.bind("<Configure>", self.on_resize)

        # if the recent files path does not exist, create it
        if not os.path.exists(os.path.dirname(self.recent_files_path)):
            self.save_recent_files()
        self.define_recent_files()

        # self.toolbar = ctk.CTkFrame(self)
        # self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # open_icon = ctk.CTkImage(Image.open('icons/open_files.png'), size=(26, 26))
        # open_button = ctk.CTkButton(self.toolbar, text='', image=open_icon, command=self.open_file) 
        # open_button.pack(side=tk.LEFT, padx=2, pady=2)

        # recent_icon = ctk.CTkImage(Image.open('icons/recent_files.png'), size=(26, 26))
        # recent_button = ctk.CTkButton(self.toolbar, text='', image=recent_icon, command=self.show_recent_files)
        # recent_button.pack(side=tk.LEFT, padx=2, pady=2)

        # quit_icon = ctk.CTkImage(Image.open('icons/quit.png'), size=(26, 26))
        # quit_button = ctk.CTkButton(self.toolbar, text='Quitter', image=quit_icon, command=self.quit)
        # quit_button.pack(side=tk.LEFT, padx=2, pady=2)

    def show_recent_files(self):
        """Show the recent files menu."""
        self.recent_files_menu.post(self.toolbar.winfo_rootx(), self.toolbar.winfo_rooty() + self.toolbar.winfo_height())

    def on_closing(self):
        """Handle the closing of the application."""
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            if hasattr(self, 'quantile_canvas'):
                self.quantile_canvas.get_tk_widget().destroy()
                self.timesteps_canvas.get_tk_widget().destroy()
                self.timesteps_frame.destroy()
            self.destroy()
            self.quit()

    def configure_ui(self):
        """Configure the UI for the application."""
        self.title(f"DEPlot - {self.file_path} - {self.models[0]} vs {self.models[1]}")
        self.numerical_filters = {}
        self.categorical_filters = {}
        self.datetime_filters = {}
        self.filtered_data = self.data.copy()
        self.last_plot_params = {'quantiles': 10, 'quantile_to_plot': 0, 'min': -1, 'max': -1}
        if hasattr(self, 'quantile_slider_frame'):
            self.quantile_canvas.get_tk_widget().destroy()
            self.timesteps_canvas.get_tk_widget().destroy()
            self.quantile_toolbar.destroy()
            self.timesteps_toolbar.destroy()
            # change the min and max values of the timesteps slider
            self.timesteps_slider.configure(from_=self.data[self.target_name].min(), to=self.data[self.target_name].max())
            self.timesteps_slider_values = (self.data[self.target_name].min(), self.data[self.target_name].max())
            self.quantile_slider.configure(from_=1, to=100)
            self.quantile_slider_value = 10
            self.timesteps_slider_label.configure(text=f'{self.target_name} range')
            self.update_timesteps_left_entry
        else:
            variables_menu = tk.Menu(self.menubar, tearoff=0)
            variables_menu.add_command(label="Select variables", command=self.show_variables_selection_window)
            variables_menu.add_command(label="Change target variable", command=self.change_target_variable)
            variables_menu.add_command(label="Change models to compare", command=self.detect_models)
            self.menubar.add_cascade(label="View", menu=variables_menu)
            self.left_frame = ctk.CTkFrame(self, fg_color='#434343')
            self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

            self.right_frame = ctk.CTkFrame(self, fg_color='#434343')
            self.right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

            # Quantile Slider
            self.quantile_slider_value = tk.IntVar()
            self.quantile_slider_frame = ctk.CTkFrame(self.left_frame, corner_radius=0)
            self.quantile_slider_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            self.quantile_slider_label = ctk.CTkLabel(self.quantile_slider_frame, text='Number of quantiles', font=('Helvetica', 20))
            self.quantile_slider_label.pack(side=tk.TOP, pady=12)

            self.quantile_slider_entry = ctk.CTkEntry(self.quantile_slider_frame, width=50)
            self.quantile_slider_entry.pack(side=tk.TOP, pady=5)
            self.quantile_slider_entry.bind('<FocusOut>', self.update_quantile_slider)
            self.quantile_slider_entry.bind('<Return>', self.update_quantile_slider)
            self.quantile_slider_entry.insert(0, '10')

            self.quantile_slider_value_left = ctk.CTkLabel(self.quantile_slider_frame, text='1')
            self.quantile_slider_value_left.pack(side=tk.LEFT, padx=10)

            self.quantile_slider = ctk.CTkSlider(self.quantile_slider_frame, from_=1, to=100, orientation='horizontal', command=self.update_quantile_slider, variable=self.quantile_slider_value)
            self.quantile_slider.pack(side=tk.TOP, fill=tk.X, pady=15, padx=10)
            self.quantile_slider.bind('<ButtonRelease-1>', self.update_quantile_plot)
            self.quantile_slider.configure(state='disabled')

            self.quantile_slider_value_right = ctk.CTkLabel(self.quantile_slider_frame, text='100')
            self.quantile_slider_value_right.pack(side=tk.RIGHT, padx=10)

            self.simulate_button = ctk.CTkButton(self.quantile_slider_frame, text='Auto-scroll')
            self.simulate_button.pack(side=tk.BOTTOM, pady=10)

            # Display mode
            self.display_mode = tk.StringVar(value="target")

            self.display_mode_frame = ctk.CTkFrame(self.right_frame, corner_radius=0)
            self.display_mode_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            self.display_mode_label = ctk.CTkLabel(self.display_mode_frame, text="Display Mode", font=('Helvetica', 15))
            self.display_mode_label.pack(side=tk.TOP, pady=5)

            self.radio_target = ctk.CTkRadioButton(self.display_mode_frame, text="Target", variable=self.display_mode, value="target", command=self.update_display_mode)
            self.radio_target.pack(side=tk.TOP, padx=5, pady=5)

            self.radio_timesteps = ctk.CTkRadioButton(self.display_mode_frame, text="Time steps", variable=self.display_mode, value="timesteps", command=self.update_display_mode)
            self.radio_timesteps.pack(side=tk.TOP, padx=5, pady=5)
            if self.individual_name is None:
                self.radio_timesteps.configure(state='disabled')

            self.convex_hull_percentage = tk.StringVar(value="80")
            self.convex_hull_frame = ctk.CTkFrame(self.right_frame, corner_radius=0)
            self.convex_hull_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            self.convex_hull_label = ctk.CTkLabel(self.convex_hull_frame, text='Convex Hull Percentage', font=('Helvetica', 15))
            self.convex_hull_label.pack(side=tk.TOP, pady=5)

            self.convex_hull_spinbox = IntSpinbox(self.convex_hull_frame, from_=0, to=100, textvariable=self.convex_hull_percentage, command=self.update_convex_hull_percentage)
            self.convex_hull_spinbox.pack(side=tk.TOP, pady=5)
            
            # Timesteps Slider
            self.timesteps_frame = ctk.CTkFrame(self.right_frame, corner_radius=0)
            self.timesteps_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

            self.timesteps_slider_values = (tk.DoubleVar(value=float(self.data[self.target_name].min())), tk.DoubleVar(value=float(self.data[self.target_name].max())))
            self.timesteps_slider_label = ctk.CTkLabel(self.timesteps_frame, text=f'{self.target_name} range', font=('Helvetica', 20))
            self.timesteps_slider_label.pack(side=tk.TOP, pady=5)

            self.timesteps_slider = CTkRangeSlider(self.timesteps_frame, orientation='horizontal', from_=float(self.data[self.target_name].min()), to=float(self.data[self.target_name].max()), variables=self.timesteps_slider_values, command=self.update_timesteps_slider, width=600)
            self.timesteps_slider.bind("<ButtonRelease-1>", self.update_timesteps_plot)
            self.timesteps_slider.pack(side=tk.TOP, padx=10, pady=10)
            self.timesteps_slider.configure(state='disabled')

            self.timesteps_slider_left = ctk.CTkEntry(self.timesteps_frame, width=50)
            self.timesteps_slider_left.pack(side=tk.LEFT, padx=80, pady=10)
            self.timesteps_slider_left.insert(0, str(self.data[self.target_name].min()))
            self.timesteps_slider_left.bind('<FocusOut>', self.update_timesteps_left_entry)
            self.timesteps_slider_left.bind('<Return>', self.update_timesteps_left_entry)

            self.timesteps_slider_right = ctk.CTkEntry(self.timesteps_frame, width=50)
            self.timesteps_slider_right.pack(side=tk.RIGHT, padx=80, pady=10)
            self.timesteps_slider_right.insert(0, str(self.data[self.target_name].max()))
            self.timesteps_slider_right.bind('<FocusOut>', self.update_timesteps_right_entry)
            self.timesteps_slider_right.bind('<Return>', self.update_timesteps_right_entry)

        # Create figure and canvas for quantile evolution
        self.quantile_fig, self.quantile_ax = plt.subplots(figsize=(8, 8))
        self.quantile_canvas = FigureCanvasTkAgg(self.quantile_fig, master=self.left_frame)
        self.quantile_toolbar = NavToolbar(self.quantile_canvas, self.left_frame)
        self.quantile_canvas.draw()
        self.quantile_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.quantile_fig.set_facecolor('#4a4a4a')
        # set all spines and ticks to white
        for spine in self.quantile_ax.spines.values():
            spine.set_edgecolor('white')
        self.quantile_ax.tick_params(axis='x', colors='white')
        self.quantile_ax.tick_params(axis='y', colors='white')
        
        # Create figure and canvas for timesteps
        self.timesteps_fig, self.timesteps_ax = plt.subplots(figsize=(9, 9))
        self.timesteps_canvas = FigureCanvasTkAgg(self.timesteps_fig, master=self.right_frame)
        self.timesteps_toolbar = NavToolbar(self.timesteps_canvas, self.right_frame)
        self.timesteps_canvas.draw()
        self.timesteps_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.timesteps_fig.set_facecolor('#4a4a4a')
        # set all spines and ticks to white
        for spine in self.timesteps_ax.spines.values():
            spine.set_edgecolor('white')
        self.timesteps_ax.tick_params(axis='x', colors='white')
        self.timesteps_ax.tick_params(axis='y', colors='white')

        self.selected_box = None

        self.quantile_slider.configure(state='normal')
        self.timesteps_slider.configure(state='normal')
        self.update_idletasks()

    def update_convex_hull_percentage(self):
        """Update the convex hull percentage."""
        self.convex_hull_percentage.set(int(self.convex_hull_spinbox.get()))
        self.update_timesteps_plot(None)
        
    def open_file(self):
        """Open a file dialog to select a CSV file."""
        file_path = filedialog.askopenfilename(filetypes=[('CSV files', '*.csv')])
        if file_path:
            self.show_dataframe_preview(file_path)

    #### DATAFRAME PREVIEW ####
    def show_dataframe_preview(self, file_path : str):
        """Show a preview of the dataframe contained in the CSV file."""
        self.file_path = file_path
        self.dataframe_preview = ctk.CTkToplevel(self)
        self.dataframe_preview.title(f'Preview of CSV file - {file_path}')
        self.dataframe_preview.geometry('1200x600')

        left_frame = ctk.CTkFrame(self.dataframe_preview)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        separator_label = ctk.CTkLabel(left_frame, text='Separator:')
        separator_label.pack(anchor='w')
        separator_entry = ctk.CTkEntry(left_frame, width=50)
        separator_entry.insert(0, ',')
        separator_entry.pack(anchor='w', fill=tk.X)

        index_var = ctk.BooleanVar()
        index_check = ctk.CTkCheckBox(left_frame, text="Contains an index column", variable=index_var, command=lambda: update_preview(index_var.get()))
        index_check.pack(anchor='w')

        individual_label = ctk.CTkLabel(left_frame, text='Individual:')
        individual_label.pack(anchor='w')
        individual_combobox = ctk.CTkComboBox(left_frame, state='readonly', values=['None'], command=lambda event: self.update_individual_name(individual_combobox.get()))
        individual_combobox.pack(anchor='w', fill=tk.X)

        target_label = ctk.CTkLabel(left_frame, text='Target:')
        target_label.pack(anchor='w')
        target_combobox = ctk.CTkComboBox(left_frame, state='readonly', values=[], command=lambda event: self.update_target_name(target_combobox.get()))
        target_combobox.pack(anchor='w', fill=tk.X)

        validate_button = ctk.CTkButton(left_frame, text='Confirm', command=self.detect_models)
        validate_button.pack(anchor='w', pady=10)

        right_frame = ctk.CTkFrame(self.dataframe_preview)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tree_frame = ctk.CTkFrame(right_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        hsb = ctk.CTkScrollbar(tree_frame, orientation='horizontal')

        tree = Treeview(tree_frame, xscrollcommand=hsb.set)
        hsb.configure(command=tree.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        tree.pack(fill=tk.BOTH, expand=True)

        def update_preview(index=False, update_combobox=False):
            """Update the preview of the dataframe."""
            separator = separator_entry.get()
            if separator != '':
                self.sep = separator
                self.has_index = index
                try:
                    self.df = pd.read_csv(file_path, sep=separator, index_col=None if not index else 0)
                    if 'Unnamed: 0' in self.df.columns:
                        self.df.rename(columns={'Unnamed: 0': 'index'}, inplace=True)
                    tree['columns'] = list(self.df.columns)
                    tree['show'] = 'headings'

                    for col in self.df.columns:
                        tree.heading(col, text=col)
                        tree.column(col, anchor='center')

                    for row in tree.get_children():
                        tree.delete(row)

                    for _, row in self.df.head(5).iterrows():
                        tree.insert('', 'end', values=list(row))

                    individual_combobox.configure(values = ['None'] + list(self.df.columns))
                    target_combobox.configure(values = list(self.df.columns))
                    if update_combobox:
                        individual_combobox.set('None')
                        self.update_individual_name('None')
                        self.update_target_name(list(self.df.columns)[2])
                        target_combobox.set(list(self.df.columns)[2])

                except Exception as e:
                    messagebox.showerror('Error', f'Failed to read CSV file: {e}')

        separator_entry.bind('<KeyRelease>', lambda event: update_preview(index_var.get(), True))
        update_preview(update_combobox=True)
        self.dataframe_preview.after(100, self.dataframe_preview.lift)
        self.dataframe_preview.after(100, self.dataframe_preview.focus_force)

    def update_individual_name(self, individual_name):
        """Update the individual name."""
        self.individual_name = individual_name

    def update_target_name(self, target_name):
        """Update the target name."""
        self.target_name = target_name
    
    #### VARIABLES SELECTION ####
    def show_variables_selection_window(self):
        if hasattr(self, 'variables_selection_window') and self.variables_selection_window.winfo_exists():
            self.variables_selection_window.lift()
            return
        
        variables = [col for col in self.data.columns if 'error' not in col and col != self.individual_name and self.target_name not in col]
        categorical_vars = [col for col in variables if self.data[col].dtype == 'object' and 'date' not in col.lower()]
        numerical_vars = [col for col in variables if self.data[col].dtype in ['int64', 'float64']]
        datetime_vars = [col for col in variables if self.data[col].dtype == 'datetime64[ns]' or 'date' in col.lower()]

        if not categorical_vars and not numerical_vars and not datetime_vars:
            messagebox.showerror('Error', 'No variables to select.')
            return

        self.variables_selection_window = ctk.CTkToplevel(self)
        self.variables_selection_window.title(f'Select the variables to filter')
        self.variables_selection_window.geometry('800x600')  # Augmenter la largeur pour inclure le panneau de récapitulatif

        variables = [col for col in self.data.columns if 'error' not in col and col != self.individual_name and self.target_name not in col]
        categorical_vars = [col for col in variables if self.data[col].dtype == 'object' and 'date' not in col.lower()]
        numerical_vars = [col for col in variables if self.data[col].dtype in ['int64', 'float64']]
        datetime_vars = [col for col in variables if self.data[col].dtype == 'datetime64[ns]' or 'date' in col.lower()]

        left_frame = ctk.CTkFrame(self.variables_selection_window)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        self.selection_frame = ctk.CTkFrame(self.variables_selection_window)
        self.selection_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.summary_frame = ctk.CTkFrame(self.variables_selection_window)
        self.summary_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        summary_label = ctk.CTkLabel(self.summary_frame, text='Summary of Filters', font=('Helvetica', 20))
        summary_label.pack(side=tk.TOP, pady=10)

        self.summary_tree = Treeview(self.summary_frame, columns=('Variable', 'Filter'), show='headings')
        self.summary_tree.heading('Variable', text='Variable')
        self.summary_tree.heading('Filter', text='Filter')
        self.summary_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.categorical_frame = ctk.CTkFrame(left_frame)
        self.categorical_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        categorical_label = ctk.CTkLabel(self.categorical_frame, text='Categorical variables', font=('Helvetica', 20))
        categorical_label.pack(side=tk.TOP, pady=10)

        self.categorical_tree = Treeview(self.categorical_frame, height=len(categorical_vars))
        self.categorical_tree['columns'] = ['values']
        self.categorical_tree['show'] = 'headings'

        self.categorical_tree.heading('values', text='Values')
        self.categorical_tree.column('values', anchor='center')

        self.numerical_frame = ctk.CTkFrame(left_frame)
        self.numerical_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        numerical_label = ctk.CTkLabel(self.numerical_frame, text='Numerical variables', font=('Helvetica', 20))
        numerical_label.pack(side=tk.TOP, pady=10)

        self.numerical_tree = Treeview(self.numerical_frame, height=len(numerical_vars))
        self.numerical_tree['columns'] = ['values']
        self.numerical_tree['show'] = 'headings'

        self.numerical_tree.heading('values', text='Values')
        self.numerical_tree.column('values', anchor='center')

        self.datetime_frame = ctk.CTkFrame(left_frame)
        self.datetime_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        datetime_label = ctk.CTkLabel(self.datetime_frame, text='Datetime variables', font=('Helvetica', 20))
        datetime_label.pack(side=tk.TOP, pady=10)

        self.datetime_tree = Treeview(self.datetime_frame, height=len(datetime_vars))
        self.datetime_tree['columns'] = ['values']
        self.datetime_tree['show'] = 'headings'

        self.datetime_tree.heading('values', text='Values')
        self.datetime_tree.column('values', anchor='center')

        self.numerical_tree.bind('<<TreeviewSelect>>', self.on_numerical_select)
        self.datetime_tree.bind('<<TreeviewSelect>>', self.on_datetime_select)
        self.categorical_tree.bind('<<TreeviewSelect>>', self.on_categorical_select)

        for var in numerical_vars:
            self.numerical_tree.insert('', 'end', values=[var])

        for var in datetime_vars:
            self.datetime_tree.insert('', 'end', values=[var])

        for var in categorical_vars:
            self.categorical_tree.insert('', 'end', values=[var])

        self.numerical_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.datetime_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.categorical_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    def on_numerical_select(self, event):
        self.clear_treeview_selection(self.datetime_tree, self.categorical_tree)
        selected_items = event.widget.selection()
        if not selected_items:
            return
        selected_item = selected_items[0]
        var = event.widget.item(selected_item, 'values')[0]
        self.show_numerical_filter_widgets(var)

    def on_datetime_select(self, event):
        self.clear_treeview_selection(self.numerical_tree, self.categorical_tree)
        selected_items = event.widget.selection()
        if not selected_items:
            return
        selected_item = selected_items[0]
        var = event.widget.item(selected_item, 'values')[0]
        self.show_datetime_filter_widgets(var)

    def on_categorical_select(self, event):
        self.clear_treeview_selection(self.numerical_tree, self.datetime_tree)
        selected_items = event.widget.selection()
        if not selected_items:
            return
        selected_item = selected_items[0]
        var = event.widget.item(selected_item, 'values')[0]
        self.show_categorical_filter_widgets(var)

    def clear_treeview_selection(self, *treeviews):
        for treeview in treeviews:
            for item in treeview.selection():
                treeview.selection_remove(item)

    def show_numerical_filter_widgets(self, var):
        for widget in self.selection_frame.winfo_children():
            widget.destroy()
        min_val, max_val = self.get_min_max_values(var)
        numerical_frame = ctk.CTkFrame(self.selection_frame, width=50)
        numerical_frame.pack(side=tk.TOP, fill=tk.X, expand=True)
        min_label = ctk.CTkLabel(numerical_frame, text=f"Min")
        min_label.pack(side=tk.LEFT)
        max_label = ctk.CTkLabel(numerical_frame, text=f"Max")
        max_label.pack(side=tk.RIGHT)
        
        self.numerical_slider_values = (tk.DoubleVar(value=min_val), tk.DoubleVar(value=max_val))
        if var in self.numerical_filters:
            self.numerical_slider_values = (tk.DoubleVar(value=self.numerical_filters[var]['min']), tk.DoubleVar(value=self.numerical_filters[var]['max']))
        numerical_slider = CTkRangeSlider(numerical_frame, from_=min_val, to=max_val, variables=self.numerical_slider_values, command=lambda val, var=var: self.update_numerical_filter(var, val))
        numerical_slider.pack(side=tk.TOP, fill=tk.X, expand=True)

        self.numerical_slider_left = ctk.CTkEntry(numerical_frame, width=50)
        self.numerical_slider_left.pack(side=tk.LEFT, padx=10, pady=10)
        self.numerical_slider_left.insert(0, str(self.numerical_slider_values[0].get()))
        self.numerical_slider_left.bind('<FocusOut>', lambda event: self.update_numerical_slider_left_entry(var))
        self.numerical_slider_left.bind('<Return>', lambda event: self.update_numerical_slider_left_entry(var))

        self.numerical_slider_right = ctk.CTkEntry(numerical_frame, width=50)
        self.numerical_slider_right.pack(side=tk.RIGHT, padx=10, pady=10)
        self.numerical_slider_right.insert(0, str(self.numerical_slider_values[1].get()))
        self.numerical_slider_right.bind('<FocusOut>', lambda event: self.update_numerical_slider_right_entry(var))
        self.numerical_slider_right.bind('<Return>', lambda event: self.update_numerical_slider_right_entry(var))

    def show_categorical_filter_widgets(self, var):
        for widget in self.selection_frame.winfo_children():
            widget.destroy()
        categories = self.get_categories(var)
        self.categorical_checkboxes = {}  # Dictionnaire pour stocker les cases à cocher
        for category in categories:
            category_var = tk.BooleanVar()
            category_var.set(category in self.categorical_filters.get(var, set()))
            category_check = ctk.CTkCheckBox(self.selection_frame, text=category, variable=category_var, command=lambda var=var, cat=category, category_var=category_var: self.update_categorical_filter(var, cat, category_var.get()))
            category_check.pack(side=tk.TOP, fill=tk.X, expand=False, pady=0)
            self.categorical_checkboxes[category] = category_check  # Stocker la case à cocher
    
    def show_datetime_filter_widgets(self, var):
        for widget in self.selection_frame.winfo_children():
            widget.destroy()
        min_date, max_date = pd.to_datetime(self.get_min_max_dates(var))
        date_frame = ctk.CTkFrame(self.selection_frame)
        date_frame.pack(side=tk.TOP, fill=tk.X, expand=False)
        
        min_label = ctk.CTkLabel(date_frame, text=f"Start Date ({var}):")
        min_label.pack(side=tk.TOP)
        self.start_date_calendar = Calendar(date_frame, mindate=min_date, maxdate=max_date)
        self.start_date_calendar.pack(side=tk.TOP)
        self.start_date_calendar.selection_set(self.datetime_filters.get(var, {}).get('start', min_date))
        self.start_date_calendar.bind("<<CalendarSelected>>", lambda event: self.update_datetime_filter_start(var))

        max_label = ctk.CTkLabel(date_frame, text=f"End Date ({var}):")
        max_label.pack(side=tk.TOP)
        self.end_date_calendar = Calendar(date_frame, mindate=min_date, maxdate=max_date)
        self.end_date_calendar.pack(side=tk.TOP)
        self.end_date_calendar.selection_set(self.datetime_filters.get(var, {}).get('end', max_date))
        self.end_date_calendar.bind("<<CalendarSelected>>", lambda event: self.update_datetime_filter_end(var))

    def get_min_max_dates(self, var):
        """ Get the minimum and maximum dates for a datetime variable. """
        var_date = pd.to_datetime(self.data[var])
        min_date = var_date.min()
        max_date = var_date.max()
        return min_date, max_date
    
    def update_datetime_filter_start(self, var):
        """ Update the filter for a datetime variable. """
        start_date = self.start_date_calendar.selection_get()
        if var not in self.datetime_filters:
            self.datetime_filters[var] = {'start': None, 'end': None}
        self.datetime_filters[var]['start'] = start_date
        self.end_date_calendar.configure(mindate=start_date)
        self.apply_filters()
        self.update_summary(var)

    def update_datetime_filter_end(self, var):
        """ Update the filter for a datetime variable. """
        end_date = self.end_date_calendar.selection_get()
        if var not in self.datetime_filters:
            self.datetime_filters[var] = {'start': None, 'end': None}
        self.datetime_filters[var]['end'] = end_date
        self.start_date_calendar.configure(maxdate=end_date)
        self.apply_filters()
        self.update_summary(var)

    def update_numerical_slider_left_entry(self, var):
        """Update the left entry of the numerical slider."""
        try:
            selected_value = float(self.numerical_slider_left.get())
            min_val, _ = self.get_min_max_values(var)
            if selected_value < min_val:
                selected_value = min_val
                self.numerical_slider_left.delete(0, tk.END)
                self.numerical_slider_left.insert(0, str(min_val))
            if selected_value < self.numerical_slider_values[1].get():
                self.numerical_slider_values[0].set(selected_value)
                self.update_numerical_filter(var, (selected_value, self.numerical_slider_values[1].get()))
            else:
                self.numerical_slider_left.delete(0, tk.END)
                self.numerical_slider_left.insert(0, str(self.numerical_slider_values[0].get()))
        except ValueError:
            self.numerical_slider_left.delete(0, tk.END)
            self.numerical_slider_left.insert(0, str(self.numerical_slider_values[0].get()))

    def update_numerical_slider_right_entry(self, var):
        """Update the right entry of the numerical slider."""
        try:
            selected_value = float(self.numerical_slider_right.get())
            _, max_val = self.get_min_max_values(var)
            if selected_value > max_val:
                selected_value = max_val
                self.numerical_slider_right.delete(0, tk.END)
                self.numerical_slider_right.insert(0, str(max_val))
            if selected_value > self.numerical_slider_values[0].get():
                self.numerical_slider_values[1].set(selected_value)
                self.update_numerical_filter(var, (self.numerical_slider_values[0].get(), selected_value))
            else:
                self.numerical_slider_right.delete(0, tk.END)
                self.numerical_slider_right.insert(0, str(self.numerical_slider_values[1].get()))
        except ValueError:
            self.numerical_slider_right.delete(0, tk.END)
            self.numerical_slider_right.insert(0, str(self.numerical_slider_values[1].get()))

    def update_numerical_filter(self, var, values):
        """ Update the filter for a numerical variable. """
        if var not in self.numerical_filters:
            self.numerical_filters[var] = {'min': None, 'max': None}
        self.numerical_filters[var]['min'], self.numerical_filters[var]['max'] = values
        self.numerical_slider_left.delete(0, tk.END)
        self.numerical_slider_left.insert(0, str(values[0]))
        self.numerical_slider_right.delete(0, tk.END)
        self.numerical_slider_right.insert(0, str(values[1]))
        self.apply_filters()
        self.update_summary(var)

    def get_min_max_values(self, var):
        """ Get the minimum and maximum values for a numerical variable. """
        min_val = self.data[var].min()
        max_val = self.data[var].max()
        return min_val, max_val

    def get_categories(self, var):
        """ Get the categories for a categorical variable. """
        return self.data[var].unique()

    def update_categorical_filter(self, var, category, selected):
        """ Update the filter for a categorical variable. """
        if var not in self.categorical_filters:
            self.categorical_filters[var] = set()
        if selected:
            self.categorical_filters[var].add(category)
        else:
            self.categorical_filters[var].discard(category)
        self.apply_filters()
        self.update_summary(var)

    def apply_filters(self):
        """ Apply the filters to the data. """
        self.filtered_data = self.data.copy()
        for var, bounds in self.numerical_filters.items():
            if bounds['min'] is not None:
                self.filtered_data = self.filtered_data[self.filtered_data[var] >= bounds['min']]
            if bounds['max'] is not None:
                self.filtered_data = self.filtered_data[self.filtered_data[var] <= bounds['max']]
        for var, categories in self.categorical_filters.items():
            if categories:
                self.filtered_data = self.filtered_data[self.filtered_data[var].isin(categories)]
        for var, dates in self.datetime_filters.items():
            if dates['start'] is not None:
                start_date = pd.to_datetime(dates['start'])
                self.filtered_data = self.filtered_data[pd.to_datetime(self.filtered_data[var]) >= start_date]
            if dates['end'] is not None:
                end_date = pd.to_datetime(dates['end'])
                self.filtered_data = self.filtered_data[pd.to_datetime(self.filtered_data[var]) <= end_date]
        self.update_display()

    def create_remove_button(self, item, var, filter_desc):
        """Create a remove button for the filter summary."""
        button = ctk.CTkButton(self.summary_tree, text='-', width=20, command=lambda: self.remove_summary(var, filter_desc))
        self.summary_tree.set(item, column='Filter', value=f"{filter_desc}    ")
        self.summary_tree.update_idletasks()
        button.place(x=self.summary_tree.bbox(item, column='Filter')[2] - 20, y=self.summary_tree.bbox(item, column='Filter')[1])
        if var in self.categorical_filters:
            button.configure(command=lambda: self.remove_summary(var, filter_desc, button))
        else:
            button.configure(command=lambda: [self.update_sliders(var), self.remove_summary(var, filter_desc), button.destroy()])
        return button

    def update_sliders(self, var):
        """Update the sliders to reset the display to default."""
        if var in self.numerical_filters:
            self.numerical_slider_left.delete(0, tk.END)
            self.numerical_slider_left.insert(0, str(self.get_min_max_values(var)[0]))
            self.numerical_slider_right.delete(0, tk.END)
            self.numerical_slider_right.insert(0, str(self.get_min_max_values(var)[1]))
            self.numerical_slider_values[0].set(self.get_min_max_values(var)[0])
            self.numerical_slider_values[1].set(self.get_min_max_values(var)[1])
        elif var in self.datetime_filters:
            self.start_date_calendar.selection_set(self.get_min_max_dates(var)[0])
            self.end_date_calendar.selection_set(self.get_min_max_dates(var)[1])

    def update_summary(self, var=None, filter_desc=""):
        """Update the summary of filters."""
        if var is None:
            self.summary_tree.delete(*self.summary_tree.get_children())
            for var in self.numerical_filters:
                filter_desc = f"Min: {self.numerical_filters[var]['min']}, Max: {self.numerical_filters[var]['max']}"
                item = self.summary_tree.insert('', 'end', values=(var, filter_desc))
                self.create_remove_button(item, var, filter_desc)
            for var in self.datetime_filters:
                filter_desc = f"Start: {self.datetime_filters[var]['start']}, End: {self.datetime_filters[var]['end']}"
                item = self.summary_tree.insert('', 'end', values=(var, filter_desc))
                self.create_remove_button(item, var, filter_desc)
            for var in self.categorical_filters:
                if self.categorical_filters[var]:
                    filter_desc = f"Categories: {', '.join(self.categorical_filters[var])}"
                    item = self.summary_tree.insert('', 'end', values=(var, filter_desc))
                    self.create_remove_button(item, var, filter_desc)
            return

        if var in self.numerical_filters:
            filter_desc = filter_desc or f"Min: {self.numerical_filters[var]['min']}, Max: {self.numerical_filters[var]['max']}"
        elif var in self.datetime_filters:
            filter_desc = filter_desc or f"Start: {self.datetime_filters[var]['start']}, End: {self.datetime_filters[var]['end']}"
        elif var in self.categorical_filters:
            if not self.categorical_filters[var]:
                self.remove_summary(var)
                return
            filter_desc = filter_desc or f"Categories: {', '.join(self.categorical_filters[var])}"
        for item in self.summary_tree.get_children():
            if self.summary_tree.item(item, 'values')[0] == var:
                self.summary_tree.item(item, values=(var, filter_desc))
                return
        item = self.summary_tree.insert('', 'end', values=(var, filter_desc))
        self.create_remove_button(item, var, filter_desc)

    def remove_summary(self, var, filter_desc=None, button=None):
        """Remove the filter from the summary."""
        if var in self.categorical_filters and self.categorical_filters[var]:
            categories = list(self.categorical_filters[var])
            if len(categories) > 1:
                menu = Menu(self, tearoff=0)
                for category in categories:
                    menu.add_command(label=f"Remove {category}", command=lambda var=var, cat=category: self.remove_category(var, cat))
                menu.post(self.winfo_pointerx(), self.winfo_pointery())
                return
            else:
                self.update_categorical_filter(var, categories[0], False)
                if button:
                    button.destroy()
                    self.remove_category(var, categories[0])
        else:
            for item in self.summary_tree.get_children():
                if self.summary_tree.item(item, 'values')[0] == var:
                    self.summary_tree.delete(item)
                    break
            # Remove the filter from the numerical, categorical, or datetime filters
            if var in self.numerical_filters:
                self.numerical_filters[var]['min'] = None
                self.numerical_filters[var]['max'] = None
                del self.numerical_filters[var]
            elif var in self.datetime_filters:
                if "Start" in filter_desc:
                    self.datetime_filters[var]['start'] = None
                if "End" in filter_desc:
                    self.datetime_filters[var]['end'] = None
                if self.datetime_filters[var]['start'] is None and self.datetime_filters[var]['end'] is None:
                    del self.datetime_filters[var]
        self.apply_filters()
        self.update_summary()

    def remove_category(self, var, category):
        """Remove a category from the categorical filter and update the checkbox."""
        self.update_categorical_filter(var, category, False)
        if category in self.categorical_checkboxes:
            self.categorical_checkboxes[category].deselect()

    def update_display(self):
        """ Update the display with the filtered data. """
        self.clear_last_plot()
        if self.timesteps_axes is not None:
            self.timesteps_axes = self.plot_timesteps(**self.last_plot_params)

    def detect_models(self):
        """ Detect the models in the dataframe. """
        if self.data is None:
            self.data = self.df
            self.all_models = [col.split('error_')[1] for col in self.data.columns if 'error_' in col]
            if self.target_name is None:
                messagebox.showerror('Error', 'Please select a target column.')
            elif len(self.all_models) < 2:
                messagebox.showerror('Error', "The file does not contain enough models or is in the wrong format.")
            else:
                if self.individual_name not in self.data.columns:
                    self.individual_name = None
                self.dataframe_preview.destroy()
        else:
            self.all_models = [col.split('error_')[1] for col in self.data.columns if 'error_' in col]
        self.show_model_selection_window()

    def show_model_selection_window(self):
        """Show the window to select the models to compare."""
        self.selection_window = ctk.CTkToplevel(self)
        self.selection_window.title('Select the models to compare')

        ctk.CTkLabel(self.selection_window, text='Select two models to compare:').pack(pady=10)

        self.model_vars = {model: tk.BooleanVar() for model in self.all_models}

        def update_checkboxes():
            """Enable or disable checkboxes based on the number of selected models."""
            selected_count = sum(var.get() for var in self.model_vars.values())
            for model, var in self.model_vars.items():
                checkbox = self.model_checkboxes[model]
                if selected_count >= 2 and not var.get():
                    checkbox.configure(state='disabled')
                else:
                    checkbox.configure(state='normal')
            if self.model_selection_button:
                self.model_selection_button.configure(state='normal' if selected_count == 2 else 'disabled')

        self.model_checkboxes = {}
        for model, var in self.model_vars.items():
            checkbox = ctk.CTkCheckBox(self.selection_window, text=model, variable=var, command=update_checkboxes)
            checkbox.pack()
            self.model_checkboxes[model] = checkbox

        self.model_selection_button = ctk.CTkButton(self.selection_window, text='OK', command=self.validate_model_selection)
        self.model_selection_button.pack(pady=10)
        self.selection_window.after(100, self.selection_window.lift)
        self.selection_window.after(100, self.selection_window.focus_force)
        # place the window in the center of the screen
        self.selection_window.update_idletasks()
        width = self.selection_window.winfo_width()
        height = self.selection_window.winfo_height()
        x = (self.selection_window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.selection_window.winfo_screenheight() // 2) - (height // 2)
        self.selection_window.geometry(f'+{x}+{y}')

    def calculate_max_timesteps(self):
        """Calculate the maximum number of timesteps in the dataframe.
        If the dataframe has an individual name, the maximum number of timesteps is the maximum number of timesteps for an individual.
        Otherwise, the maximum number of timesteps is the length of the dataframe."""
        if self.individual_name is None:
            self.max_timesteps = len(self.data)
        else:
            self.max_timesteps = self.data.groupby(self.individual_name).size().max()

    def validate_model_selection(self):
        """Validate the model selection and configure the UI."""
        selected_models = [model for model, var in self.model_vars.items() if var.get()]
        if len(selected_models) != 2:
            messagebox.showerror('Error', 'Please select exactly two models.')
            self.selection_window.destroy()
            self.show_model_selection_window()
        else:
            self.models = selected_models
            self.separator = self.sep
            self.has_index = self.has_index
            self.timesteps_axes = None
            self.calculate_max_timesteps()
            self.selection_window.destroy()
            self.configure_ui()
            self.setup_plot_timesteps()
            self.quantile_slider.set(10)
            self.update_quantile_plot(None)
            self.save_recent_files()
            self.update_recent_files()

    def setup_plot_timesteps(self):
        """Setup the plot for the timesteps of the errors for the models on the provided axis. """
        extrema = max(
            abs(self.data[['error_'+model for model in self.models]].min().min()), 
            abs(self.data[['error_'+model for model in self.models]].max().max()))
        
        self.timesteps_ax.set_xlim(-extrema, extrema)
        self.timesteps_ax.set_ylim(-extrema, extrema)
        self.timesteps_ax.set_aspect('equal', adjustable='box')

        self.timesteps_ax.plot([0, 0], [-extrema, extrema], color='black', linewidth=1)
        self.timesteps_ax.plot([-extrema, extrema], [0, 0], color='black', linewidth=1)
        equal_points, = self.timesteps_ax.plot([-extrema, extrema], [-extrema, extrema], label="Equal absolute errors")
        self.timesteps_ax.plot([-extrema, extrema], [extrema, -extrema], color='tab:blue', linewidth=1)

        abs_better, _ = self.timesteps_ax.fill(
            [-extrema, 0, extrema], [-extrema, 0, -extrema], [-extrema, 0, extrema], [extrema, 0, extrema],  
            c='tab:orange', 
            alpha=0.2, 
            label=f'{self.models[0]} is better')
        ord_better, _ = self.timesteps_ax.fill(
            [-extrema, 0, -extrema], [-extrema, 0, extrema], [extrema, 0, extrema], [-extrema, 0, extrema], 
            c='tab:green', 
            alpha=0.2, 
            label=f'{self.models[1]} is better')
        
        x = self.data['error_'+self.models[0]]
        y = self.data['error_'+self.models[1]]

        median = (self.data['error_'+self.models[0]].median(), self.data['error_'+self.models[1]].median())
        self.timesteps_ax.plot(median[0], median[1], 'x', color='black', markersize=10, alpha=0.4)[0]

        all_points = self.timesteps_ax.scatter(x, y, s=200, alpha=0.2, color='gray', label='All points')

        self.timesteps_ax.set_xlabel(f'Errors of {self.models[0]}')
        self.timesteps_ax.set_ylabel(f'Errors of {self.models[1]}')
        self.timesteps_ax.xaxis.label.set_color('tab:orange')
        self.timesteps_ax.yaxis.label.set_color('tab:green')

        self.timesteps_ax.legend(handles=[all_points, abs_better, ord_better, equal_points], loc='lower right')
        self.colorbar = plt.colorbar(ScalarMappable(norm=Normalize(0, 100), cmap='Spectral'), ax=self.timesteps_ax)
        self.colorbar.set_label('Percentile')
        self.colorbar.ax.yaxis.label.set_color('white')
        self.colorbar.ax.yaxis.set_tick_params(color='white')
        for label in self.colorbar.ax.yaxis.get_ticklabels():
            label.set_color('white')
        # self.timesteps_fig.tight_layout()
        self.timesteps_ax.figure.canvas.draw()

    def plot_quantile_evolution(self, quantile=10, width=0.8, min_timesteps=-1, max_timesteps=-1):
        """Plot the quantile evolution on the provided axis."""
        self.quantile_ax.cla()
        
        if min_timesteps == -1 and max_timesteps == -1:
            data = self.data.copy()
        elif min_timesteps == -1:
            data = self.data.loc[:max_timesteps].copy()
        elif max_timesteps == -1:
            data = self.data.loc[min_timesteps:].copy()
        else:
            data = self.data.loc[min_timesteps:max_timesteps].copy()
        self.quantile_ax.set_xlim(0, quantile + 1)

        boxplot_data = [{}, {}]
        self.quantile_ax.axhline(y=0, color='black', linestyle='-')
        if self.individual_name is None:
            data['quantile'] = pd.qcut(data[self.target_name].rank(method='first'), quantile, labels=False) + 1
        else:
            data['quantile'] = pd.qcut(data.groupby(self.individual_name).cumcount(), quantile, labels=False) + 1
        for i in range(1, quantile + 1):
            data_per = data[data['quantile'] == i].drop(columns=['quantile'])
            boxplot_data[0][i] = data_per['error_' + self.models[0]].to_numpy()
            boxplot_data[1][i] = data_per['error_' + self.models[1]].to_numpy()

        bp1 = self.quantile_ax.boxplot(boxplot_data[0].values(), positions=sorted(list(boxplot_data[0].keys())), widths=width, patch_artist=True, showfliers=False, 
                boxprops=dict(facecolor='none', hatch='///', edgecolor='tab:orange'), medianprops=dict(color='black'))
        bp2 = self.quantile_ax.boxplot(boxplot_data[1].values(), positions=sorted(list(boxplot_data[1].keys())), widths=width, patch_artist=True, showfliers=False, 
                boxprops=dict(facecolor='none', hatch='\\\\\\', edgecolor='tab:green'), medianprops=dict(color='black'))

        self.quantile_ax.set_xticks(range(0, quantile + 1, max(1, quantile // 5)))
        self.quantile_ax.set_xticklabels(range(0, quantile + 1, max(1, quantile // 5)))

        self.quantile_ax.set_xlabel('Data Quantile')
        self.quantile_ax.set_ylabel('Errors')
        self.quantile_ax.xaxis.label.set_color('white')
        self.quantile_ax.yaxis.label.set_color('white')
        self.quantile_ax.legend([bp1['boxes'][0], bp2['boxes'][0]], self.models, loc='lower right')

        self.selected_box = None
        self.highlight_rect = None

        def on_click(event : MouseEvent):
            """Handle the click event on the boxplot."""
            if not hasattr(on_click, 'updating'):
                on_click.updating = False
            if on_click.updating:
                return
            on_click.updating = True
            try:
                # Réinitialiser la mise en surbrillance de la boxplot précédemment sélectionnée
                if self.selected_box is not None:
                    self.selected_box[0].set_facecolor('none')
                    self.selected_box[0].set_hatch('///')
                    self.selected_box[0].set_edgecolor('tab:orange')
                    self.selected_box[0].set_linewidth(1)
                    self.selected_box[1].set_facecolor('none')
                    self.selected_box[1].set_hatch('\\\\\\')
                    self.selected_box[1].set_edgecolor('tab:green')
                    self.selected_box[1].set_linewidth(1)
                select_boxplot(event)
            finally:
                on_click.updating = False

        def select_boxplot(event : MouseEvent):
            """Select the boxplot that was clicked on."""
            for i, (box1, box2) in enumerate(zip(bp1['boxes'], bp2['boxes'])):
                if box1.contains(event)[0] or box2.contains(event)[0]:
                    if self.timesteps_axes is not None:
                        for ax in self.timesteps_axes:
                            try:
                                ax.remove()
                            except:
                                pass
                    self.timesteps_axes = self.plot_timesteps(quantiles=quantile, quantile_to_plot=i+1)
                    self.selected_box = (box1, box2)
                    box1.set_facecolor((1, 0.647, 0, 0.5))
                    box1.set_edgecolor('red')
                    box1.set_linewidth(2)
                    box2.set_facecolor((0, 0.502, 0, 0.5))
                    box2.set_edgecolor('red')
                    box2.set_linewidth(2)
                    self.quantile_ax.figure.canvas.draw()
                    return

        self.quantile_ax.figure.canvas.mpl_connect('button_press_event', on_click)
        self.quantile_ax.figure.canvas.draw()

        self.simulate_button_click = self.simulate_button.configure(command=lambda: self.simulate_all_clicks(bp1['boxes']))

    def simulate_all_clicks(self, boxes, index=0):
        """Simulate all the clicks on the boxplots."""
        if not self.is_simulating:
            self.is_simulating = True
            self.quantile_slider.configure(state='disabled')
            self.timesteps_slider.configure(state='disabled')
            self.quantile_slider_entry.configure(state='disabled', fg_color='black')
            self.timesteps_slider_left.configure(state='disabled', fg_color='black')
            self.timesteps_slider_right.configure(state='disabled', fg_color='black')
            # increase the alpha of the slider
            self.quantile_slider.configure(fg_color='black', progress_color=ctk.ThemeManager.theme["CTkSlider"]["fg_color"], button_color='gray')
            self.timesteps_slider.configure(fg_color='black', progress_color=ctk.ThemeManager.theme["CTkSlider"]["fg_color"], button_color='gray')
            self.simulate_button.configure(
                text=f"Stop scrolling",
                fg_color='#dc3545',
                hover_color='#99252f',
                command=lambda: self.stop_simulation(boxes)
            )
        if index < len(boxes) and self.is_simulating:
            self.simulate_click(boxes[index])
            self.after_id = self.after(2000, lambda: self.simulate_all_clicks(boxes, index+1))
        else:
            self.simulate_button.configure(
                text=f"Auto-scroll",
                state='normal',
                fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
                hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],
                command=lambda: self.simulate_all_clicks(boxes)
            )
            self.is_simulating = False
            self.quantile_slider.configure(
                state='normal',
                fg_color=ctk.ThemeManager.theme["CTkSlider"]["fg_color"],
                progress_color=ctk.ThemeManager.theme["CTkSlider"]["progress_color"],
                button_color=ctk.ThemeManager.theme["CTkSlider"]["button_color"])
            self.timesteps_slider.configure(
                state='normal',
                fg_color=ctk.ThemeManager.theme["CTkSlider"]["fg_color"],
                progress_color=ctk.ThemeManager.theme["CTkSlider"]["progress_color"],
                button_color=ctk.ThemeManager.theme["CTkSlider"]["button_color"])
            self.quantile_slider_entry.configure(state='normal', fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])
            self.timesteps_slider_left.configure(state='normal', fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])
            self.timesteps_slider_right.configure(state='normal', fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])
            self.clear_last_plot()

    def stop_simulation(self, boxes):
        """Stop the simulation of clicks."""
        if self.is_simulating:
            self.after_cancel(self.after_id)
            self.simulate_button.configure(
                text=f"Auto-scroll",
                state='normal',
                fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"],
                hover_color=ctk.ThemeManager.theme["CTkButton"]["hover_color"],
                command=lambda: self.simulate_all_clicks(boxes))
            self.is_simulating = False
            self.quantile_slider.configure(
                state='normal',
                fg_color=ctk.ThemeManager.theme["CTkSlider"]["fg_color"],
                progress_color=ctk.ThemeManager.theme["CTkSlider"]["progress_color"],
                button_color=ctk.ThemeManager.theme["CTkSlider"]["button_color"])
            self.timesteps_slider.configure(
                state='normal',
                fg_color=ctk.ThemeManager.theme["CTkSlider"]["fg_color"],
                progress_color=ctk.ThemeManager.theme["CTkSlider"]["progress_color"],
                button_color=ctk.ThemeManager.theme["CTkSlider"]["button_color"])
            self.quantile_slider_entry.configure(state='normal', fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])
            self.timesteps_slider_left.configure(state='normal', fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])
            self.timesteps_slider_right.configure(state='normal', fg_color=ctk.ThemeManager.theme["CTkEntry"]["fg_color"])
            self.clear_last_plot()

    def simulate_click(self, box1):
        """Simulate a click event on the given boxplot."""
        path = box1.get_path()
        vertices = path.vertices
        center_x = (vertices[0][0] + vertices[2][0]) / 2
        center_y = (vertices[0][1] + vertices[2][1]) / 2

        trans = self.quantile_ax.transData.transform
        fig_x, fig_y = trans((center_x, center_y))

        event = MouseEvent(name='button_press_event', canvas=self.quantile_ax.figure.canvas, x=fig_x, y=fig_y, button=1)
        event.xdata = center_x
        event.ydata = center_y
        self.quantile_ax.figure.canvas.callbacks.process('button_press_event', event)

    def plot_timesteps(self, quantiles=10, quantile_to_plot=0, min=-1, max=-1) -> list[plt.Artist]:
        """Plot the timesteps of the errors for the models on the provided axis."""
        self.last_plot_params = {'quantiles': quantiles, 'quantile_to_plot': quantile_to_plot, 'min': min, 'max': max}
        axes = []

        data = self.filtered_data.copy()  # Use filtered data instead of original data
        if self.display_mode.get() == "timesteps" or quantiles > 1:
            if self.individual_name is not None:
                if min <= 0 and max == -1:
                    pass
                elif min <= 0:
                    data = data.groupby(self.individual_name).head(max).reset_index(drop=True)
                elif max == -1:
                    data = data.groupby(self.individual_name).tail(len(data) - min).reset_index(drop=True)
                else:
                    data = data.groupby(self.individual_name).apply(lambda x: x.iloc[min:max], include_groups=False).reset_index(drop=True)
            else:
                if min == -1 and max == -1:
                    pass
                elif min == -1:
                    data = data.loc[:max].copy()
                elif max == -1:
                    data = data.loc[min:].copy()
                else:
                    data = data.loc[min:max].copy()
        elif self.display_mode.get() == "target":
            if min is not None and max is not None:
                data = data[(data[self.target_name] >= min) & (data[self.target_name] <= max)]

        if quantiles > 1:
            if self.individual_name is None:
                data['quantile'] = pd.qcut(data[self.target_name].rank(method='first'), quantiles, labels=False) + 1
            else:
                data['quantile'] = pd.qcut(data.groupby(self.individual_name).cumcount(), quantiles, labels=False) + 1
            data_per = data[data['quantile'] == quantile_to_plot].reset_index(drop=True)
            data_per.drop(columns=['quantile'], inplace=True)
        else:
            data_per = data.reset_index(drop=True).copy()

        x_per = data_per['error_'+self.models[0]]
        y_per = data_per['error_'+self.models[1]]

        median_per = (data_per['error_'+self.models[0]].median(), data_per['error_'+self.models[1]].median())
        cov_per = np.linalg.inv(np.cov(data_per[['error_'+self.models[0], 'error_'+self.models[1]]], rowvar=False))
        distance_per = []
        for row in data_per[['error_'+self.models[0], 'error_'+self.models[1]]].values:
            distance_per.append(mahalanobis(row, median_per, cov_per))
        data_per['distance'] = distance_per

        data_per = data_per.sort_values(by='distance')
        data_per['percentile'] = data_per['distance'].apply(lambda x: (len(data_per[data_per['distance'] <= x]) / len(data_per)) * 100)
        data_per = data_per.sort_index()

        axes.append(self.timesteps_ax.scatter(x_per, y_per, s=200, c=data_per['percentile'], cmap='Spectral'))
        axes.append(self.timesteps_ax.plot(median_per[0], median_per[1], 'x', color='black', markersize=10, alpha=0.7)[0])

        # Calculate and plot the convex hull
        percentage = int(self.convex_hull_percentage.get())
        if percentage > 0:
            threshold = np.percentile(data_per['distance'], percentage)
            points_within_threshold = data_per[data_per['distance'] <= threshold][['error_'+self.models[0], 'error_'+self.models[1]]].values
            if len(points_within_threshold) > 2:
                hull = ConvexHull(points_within_threshold)
                for simplex in hull.simplices:
                    axes.append(self.timesteps_ax.plot(points_within_threshold[simplex, 0], points_within_threshold[simplex, 1], 'k-', lw=1)[0])

        if quantile_to_plot == 0 and self.display_mode.get() == "timesteps" and (min != -1 or max != -1):
            self.timesteps_ax.set_title(f'Evolution of errors from timesteps {min} to {max}')
        elif self.display_mode.get() == "target" and (min != -1 or max != -1):
            self.timesteps_ax.set_title(f'Evolution of errors for target range {min} to {max}')
        else:
            self.timesteps_ax.set_title(f'Evolution of errors for quantile {quantile_to_plot}\n'
                                        f'Values between {data_per[self.target_name].min()} and {data_per[self.target_name].max()}',
                                        fontsize=12, color='white', loc='center')
        self.timesteps_ax.title.set_color('white')

        self.timesteps_ax.figure.canvas.draw()
        return axes

    def clear_last_plot(self):
        """Remove the last plot from the timesteps axis."""
        if self.selected_box is not None:
            self.selected_box[0].set_facecolor('none')
            self.selected_box[0].set_hatch('///')
            self.selected_box[0].set_edgecolor('tab:orange')
            self.selected_box[0].set_linewidth(1)
            self.selected_box[1].set_facecolor('none')
            self.selected_box[1].set_hatch('\\\\\\')
            self.selected_box[1].set_edgecolor('tab:green')
            self.selected_box[1].set_linewidth(1)
        if self.timesteps_axes is not None:
            for ax in self.timesteps_axes:
                try:
                    ax.remove()
                except:
                    pass
        self.quantile_ax.figure.canvas.draw()
    
    def save_recent_files(self):
        """Save the recent files to a JSON file."""
        os.makedirs(os.path.dirname(self.recent_files_path), exist_ok=True)
        with open(self.recent_files_path, 'w') as f:
            json.dump(self.recent_files, f)

    def define_recent_files(self):
        """Define the recent files from the JSON file."""
        if self.recent_files_menu is not None:
            self.recent_files_menu.delete(0, 'end')
        if os.path.exists(self.recent_files_path):
            with open(self.recent_files_path, 'r') as f:
                if os.stat(self.recent_files_path).st_size == 0:
                    self.recent_files = []
                else:
                    self.recent_files = json.load(f)
                    self.recent_files.sort(key=lambda x: x['datetime'], reverse=True)
                    for file_info in self.recent_files:
                        self.recent_files_menu.add_command(label=f"{file_info['file_path']} - {file_info['models'][0]} vs {file_info['models'][1]}", command=lambda p=file_info: self.load_recent_file(p))
    
    def load_recent_file(self, file_info : dict):
        """Load a recent file."""
        try:
            file_info['datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.datetime = datetime.now()
            self.file_path = file_info['file_path']
            self.has_index = file_info['has_index']
            self.sep = file_info['sep']
            self.models = file_info['models']
            self.individual_name = file_info['individual_name']
            self.target_name = file_info['target_name']
            self.timesteps_axes = None
        except KeyError:
            messagebox.showerror('Error', 'An error occured while loading the file, please reload it.')
        self.data = pd.read_csv(self.file_path, sep=self.sep, index_col=0 if self.has_index else None)
        self.update_recent_files(file_info)
        self.calculate_max_timesteps()
        self.title(f"DEPlot - {self.file_path} - {self.models[0]} vs {self.models[1]}")
        self.configure_ui()
        self.setup_plot_timesteps()
        self.quantile_slider.set(10)
        self.update_quantile_plot(None)

    def update_recent_files(self, file_info : dict = None):
        """Update the recent files list."""
        if file_info is None:
            file_info = {
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_path': self.file_path,
                'has_index': self.has_index,
                'sep': self.sep,
                'models': self.models,
                'individual_name': self.individual_name,
                'target_name': self.target_name
            }
        if file_info not in self.recent_files:
            self.recent_files.append(file_info)
            if len(self.recent_files) > 10:
                self.recent_files.pop(0)
            self.recent_files_menu.add_command(label=f'{self.file_path} - {self.models[0]} vs {self.models[1]}', command=lambda: self.load_recent_file(file_info))
        else:
            self.recent_files.remove(file_info)
            self.recent_files.append(file_info)
            self.recent_files_menu.delete(0, 'end')
            self.recent_files.sort(key=lambda x: x['datetime'], reverse=True)
            for file_info in self.recent_files:
                self.recent_files_menu.add_command(label=f"{file_info['file_path']} - {file_info['models'][0]} vs {file_info['models'][1]}", command=lambda p=file_info: self.load_recent_file(p))
        self.save_recent_files()

    def update_quantile_slider(self, event : tk.Event):
        """Update the quantile slider value."""
        if event is None or type(event) == float:
            self.quantile_slider_value = round(self.quantile_slider.get())
            self.quantile_slider_entry.delete(0, tk.END)
            self.quantile_slider_entry.insert(0, str(self.quantile_slider_value))
        else:
            self.quantile_slider_value = int(self.quantile_slider_entry.get())
            self.quantile_slider.set(self.quantile_slider_value)
            self.update_quantile_plot(event)

    def update_timesteps_slider(self, event : tk.Event):
        """Update the timesteps slider values."""
        self.timesteps_slider_values = (self.timesteps_slider.get()[0], self.timesteps_slider.get()[1])
        # self.timesteps_slider_left.place(x=self.timesteps_slider.get()[0] * (self.timesteps_slider.winfo_width() - 20) / self.max_timesteps + 10, y=50)
        # self.timesteps_slider_right.place(x=self.timesteps_slider.get()[1] * (self.timesteps_slider.winfo_width() - 20) / self.max_timesteps + 10, y=50)
        self.update_timesteps_left_entry(event)
        self.update_timesteps_right_entry(event)

    def update_timesteps_left_entry(self, event : tk.Event):
        """Update the left entry of the timesteps slider."""
        if event is None or type(event) == tuple:
            self.timesteps_slider_left.delete(0, tk.END)
            self.timesteps_slider_left.insert(0, str(self.timesteps_slider_values[0]))
        else:
            try:
                selected_value = float(self.timesteps_slider_left.get())
                if selected_value < 0 or selected_value > self.timesteps_slider_values[1]:
                    self.timesteps_slider_left.delete(0, tk.END)
                    self.timesteps_slider_left.insert(0, str(self.timesteps_slider_values[0]))
                else:
                    self.timesteps_slider_values = (float(self.timesteps_slider_left.get()), self.timesteps_slider_values[1])
                    self.timesteps_slider.set(self.timesteps_slider_values)
                    self.update_timesteps_plot(event)
            except ValueError:
                self.timesteps_slider_left.delete(0, tk.END)
                self.timesteps_slider_left.insert(0, str(self.timesteps_slider_values[0]))

    def update_timesteps_right_entry(self, event : tk.Event):
        """Update the right entry of the timesteps slider."""
        if event is None or type(event) == tuple:
            self.timesteps_slider_right.delete(0, tk.END)
            self.timesteps_slider_right.insert(0, str(self.timesteps_slider_values[1]))
        else:
            try:
                selected_value = float(self.timesteps_slider_right.get())
                if selected_value > self.max_timesteps or selected_value < self.timesteps_slider_values[0]:
                    self.timesteps_slider_right.delete(0, tk.END)
                    self.timesteps_slider_right.insert(0, str(self.timesteps_slider_values[1]))
                else:
                    self.timesteps_slider_values = (self.timesteps_slider_values[0], float(self.timesteps_slider_right.get()))
                    self.timesteps_slider.set(self.timesteps_slider_values)
                    self.update_timesteps_plot(event)
            except ValueError:
                self.timesteps_slider_right.delete(0, tk.END)
                self.timesteps_slider_right.insert(0, str(self.timesteps_slider_values[1]))

    def update_timesteps_plot(self, event : tk.Event):
        """Update the timesteps plot."""
        min_timesteps = self.timesteps_slider_values[0]
        max_timesteps = self.timesteps_slider_values[1]
        self.clear_last_plot()
        self.timesteps_axes = self.plot_timesteps(1, min=min_timesteps, max=max_timesteps)

    def update_quantile_plot(self, event : tk.Event):
        """Update the quantile plot."""
        quantile = int(self.quantile_slider.get())
        self.plot_quantile_evolution(quantile, width=1)

    def update_display_mode(self):
        """ Switch between the two display modes: timesteps and target range."""
        if self.display_mode.get() == "timesteps":
            self.timesteps_slider_values = (0, self.max_timesteps)
            self.timesteps_slider.configure(from_=0, to=self.max_timesteps)
            self.timesteps_slider_label.configure(text='Number of time steps')
            self.update_timesteps_left_entry(None)
            self.update_timesteps_right_entry(None)
        else:
            self.timesteps_slider_values = (self.data[self.target_name].min(), self.data[self.target_name].max())
            self.timesteps_slider.configure(from_=self.data[self.target_name].min(), to=self.data[self.target_name].max())
            self.timesteps_slider_label.configure(text=f'{self.target_name} range')
            self.update_timesteps_left_entry(None)
            self.update_timesteps_right_entry(None)
        self.update_timesteps_plot(None)
        self.timesteps_slider.set(self.timesteps_slider_values)

    def on_resize(self, event : tk.Event):
        """Handle the resize event of the window."""
        if hasattr(self, 'quantile_canvas'):
            self.quantile_canvas.get_tk_widget().configure(width=self.quantile_canvas.get_tk_widget().winfo_toplevel().winfo_width() // 2 - 30)
            self.timesteps_canvas.get_tk_widget().configure(width=self.timesteps_canvas.get_tk_widget().winfo_toplevel().winfo_width() // 2 - 30)
            self.update_quantile_slider(None)
            self.update_timesteps_slider(None)

    def change_target_variable(self):
        """Permet de sélectionner une nouvelle variable target et de rafraîchir les visualisations."""
        target_window = ctk.CTkToplevel(self)
        target_window.title("Change Target Variable")
        target_window.geometry("400x200")

        ctk.CTkLabel(target_window, text="Select a new target variable:", font=("Helvetica", 15)).pack(pady=10)

        target_combobox = ctk.CTkComboBox(
            target_window,
            state="readonly",
            values=list(self.data.columns),
            command=lambda event: self.update_target_name(target_combobox.get())
        )
        target_combobox.set(self.target_name)  # Pré-sélectionner la variable actuelle
        target_combobox.pack(pady=10, fill=tk.X, padx=20)

        def confirm_target_change():
            self.target_name = target_combobox.get()
            target_window.destroy()
            self.refresh_visualizations()

        ctk.CTkButton(target_window, text="Confirm", command=confirm_target_change).pack(pady=10)

    def refresh_visualizations(self):
        """Rafraîchit toutes les visualisations en fonction de la nouvelle variable target."""
        self.filtered_data = self.data.copy()
        self.configure_ui()
        self.setup_plot_timesteps()
        self.update_quantile_plot(None)

app = QuantileApp()
app.mainloop()