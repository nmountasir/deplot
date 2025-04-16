from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import matplotlib as mpl
import os
import pathlib

class NavToolbar(NavigationToolbar2Tk):
    def __init__(self, canvas_, parent_, pack_=True):
        NavigationToolbar2Tk.__init__(self, canvas_, parent_, pack_toolbar=pack_)
        self.update()

    def save_figure(self, *args):
        # reset colors to default
        filetypes = self.canvas.get_supported_filetypes_grouped()
        tk_filetypes = [
            (name, " ".join(f"*.{ext}" for ext in exts))
            for name, exts in sorted(filetypes.items())
        ]

        default_extension = self.canvas.get_default_filetype()
        default_filetype = self.canvas.get_supported_filetypes()[default_extension]
        filetype_variable = tk.StringVar(self, default_filetype)

        # adding a default extension seems to break the
        # asksaveasfilename dialog when you choose various save types
        # from the dropdown.  Passing in the empty string seems to
        # work - JDH!
        # defaultextension = self.canvas.get_default_filetype()
        defaultextension = ''
        initialdir = os.path.expanduser(mpl.rcParams['savefig.directory'])
        # get_default_filename() contains the default extension. On some platforms,
        # choosing a different extension from the dropdown does not overwrite it,
        # so we need to remove it to make the dropdown functional.
        initialfile = pathlib.Path(self.canvas.get_default_filename()).stem
        fname = tkinter.filedialog.asksaveasfilename(
            master=self.canvas.get_tk_widget().master,
            title='Save the figure',
            filetypes=tk_filetypes,
            defaultextension=defaultextension,
            initialdir=initialdir,
            initialfile=initialfile,
            typevariable=filetype_variable
            )

        if fname in ["", ()]:
            return
        # Save dir for next time, unless empty str (i.e., use cwd).
        if initialdir != "":
            mpl.rcParams['savefig.directory'] = (
                os.path.dirname(str(fname)))

        # If the filename contains an extension, let savefig() infer the file
        # format from that. If it does not, use the selected dropdown option.
        if pathlib.Path(fname).suffix[1:] != "":
            extension = None
        else:
            extension = filetypes[filetype_variable.get()][0]

        try:
            fig = self.canvas.figure
            axis = fig.get_axes()[0]
            fig.set_facecolor('white')
            for spine in axis.spines.values():
                spine.set_edgecolor('black')
            axis.title.set_color('black')
            axis.xaxis.label.set_color('black')
            axis.yaxis.label.set_color('black')
            axis.tick_params(axis='x', colors='black')
            axis.tick_params(axis='y', colors='black')
            # get the colorbar from the figure
            if len(fig.get_axes()) > 1:
                colorbar = fig.get_axes()[1]
                colorbar.yaxis.label.set_color('black')
                colorbar.yaxis.set_tick_params(color='black')
                for label in colorbar.yaxis.get_ticklabels():
                    label.set_color('black')
                axis.xaxis.label.set_color('tab:orange')
                axis.yaxis.label.set_color('tab:green')

            fig.savefig(fname, format=extension)

            fig.set_facecolor('#4a4a4a')
            for spine in axis.spines.values():
                spine.set_edgecolor('white')
            axis.title.set_color('white')
            axis.tick_params(axis='x', colors='white')
            axis.tick_params(axis='y', colors='white')
            if len(fig.get_axes()) > 1:
                colorbar.yaxis.label.set_color('white')
                colorbar.yaxis.set_tick_params(color='white')
                for label in colorbar.yaxis.get_ticklabels():
                    label.set_color('white')
                axis.xaxis.label.set_color('tab:orange')
                axis.yaxis.label.set_color('tab:green')
        except Exception as e:
            tkinter.messagebox.showerror("Error saving file", str(e))