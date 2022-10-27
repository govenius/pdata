'''
Joonas Govenius, 2019-2022

Helper functions related to interacting with Jupyter.
'''

from pdata._metadata import __version__
import time

def in_jupyterlab():
  """ Attempt to determine whether this is being run in JupyterLab (as opposed to Notebook or console). """
  try:
    from jupyter_server.serverapp import list_running_servers # Works in JupyterLab
    servers = list(list_running_servers())
    return len(servers) > 0 # Probably running in a Notebook if no servers returned
  except ImportError:
    return False

def get_notebook_name():
  """
  Attempt to return the full path of the Jupyter notebook.
  This is expected to work if the notebook runs locally within Jupyter Notebook or Lab.
  Otherwise returns None.

  From https://github.com/jupyter/notebook/issues/1000#issuecomment-359875246
  """
  import json
  import os.path
  import re
  import ipykernel
  import requests

  from requests.compat import urljoin

  try:
    kernel_id = re.search('kernel-(.*).json',
                            ipykernel.connect.get_connection_file()).group(1)
  except RuntimeError:
    return None

  try:
    from jupyter_server.serverapp import list_running_servers # Works in JupyterLab
    servers = list(list_running_servers())
    if len(servers)==0: raise ImportError # Probably running in a Notebook then
  except ImportError:
    from notebook.notebookapp import list_running_servers # Works in Jupyter Notebook
    servers = list_running_servers()

  for ss in servers:
    response = requests.get(urljoin(ss['url'], 'api/sessions'),
                            params={'token': ss.get('token', '')})
    for nn in json.loads(response.text):
      if nn['kernel']['id'] == kernel_id:
        relative_path = nn['notebook']['path']
        full_path = os.path.join(ss['notebook_dir'] if 'notebook_dir' in ss else os.path.abspath(""),
                                 relative_path)
        if os.path.isfile(full_path): return full_path


def save_notebook():
  """
  Saves the Jupyter notebook, if this runs from Jupyter Notebook or JupyterLab.

  Based on https://stackoverflow.com/questions/44961557/how-can-i-save-a-jupyter-notebook-ipython-notebook-programmatically?rq=1
  """

  try:
    # This works in JupyterLab
    from ipylab import JupyterFrontEnd
    JupyterFrontEnd().commands.execute('docmanager:save')
    if not in_jupyterlab(): raise ImportError # Fall back to Notebook code

  except ImportError:
    # This works in Jupyter Notebook
    from IPython.display import Javascript
    from IPython.core.display import display

    display(Javascript('''
      require(["base/js/namespace"],function(Jupyter) {
          Jupyter.notebook.save_checkpoint();
      });
      '''))

  # We should wait until the save has actually been completed.
  # TODO: This is not the best way...
  time.sleep(0.5)
