Package maintenance
========================

The following guidelines are meant for future package updates by an extended user base. Please adhere to the original settings unless a significantly better version of things is available.


2.1 Main dependencies

For future updates on the **hextof-processor** package, the following main dependencies should be checked for compatibility,

* **pah** -- the library from the FLASH beamline for parsing the raw hdf5 file generated in the experiment
* **dask** -- contains the distributed version of numpy array and pandas dataframe
* **numpy**, **pandas**


2.2 How to document

Documentation of the package follows the `readthedocs <http://docs.readthedocs.io/en/latest/getting_started.html>` (a.k.a. rtd) style and uses the `sphinx rtd theme <https://github.com/rtfd/sphinx_rtd_theme>`_. The generated htmls are self-hosted on the GitHub repository. This is partially due to the fact that the current version of the **setup.py** file in **hextof-processor** cannot be properly parsed by the readthedocs webhost to be installed and hosted there. Future improvements on the code packaging side may eliminate such problem. Nevertheless, self-hosting on GitHub has its own advantage such that one may include both **rst** (reStructuredText) and **md** (Markdown) formats. In the current version of the documentation, the description of the functions and classes were generated through the docstrings, the other files are generated directly from Markdown files.

To update the documentation, follow the steps below,

(1) Install the prerequisite packages, if not yet present on your local computer.

* **sphinx** -- python rst parser package
* **sphinx_rtd_theme** -- readthedocs theme package for sphinx

(2) Have a local git-clone of the **hextof-processor** package.

(3) Update any of the documentation-related source files. These include,

* The code docstrings in the .py files under the **processor** folder.
* The rst files for formatting code docstrings, currently in the **library** subfolder of the **source** folder.
* The Markdown files of each section, currently in the **example** and **misc** subfolders of the **source** folder.
* The main index file **index.rst** under the **source** folder, which controls the formatting of the **index.html** page.
* The main configuration file **conf.py** under the **source** folder. This includes most of the basic settings in documentation such as html theme, parsers, code version, etc.
* Any other html styling files in .js or .css formats.

(4) cd into the **html** folder on the terminal and run

.. code-block:: bash

    make html


The original build contains the **Makefiles** for both Windows and Linux systems. This step initiates the build process locally on your computer. In the process, a series of messages will be generated in the terminal. Most of the times, the warnings on the formatting issues can be ignored, if they don't causing the build process to fail.

(5) Check for the local build by viewing the **index.html** file in the **html** folder and browse through the newly added changes. On special occasions, one needs to start a clean build from (almost) nothing in order to implement all the changes. In this case, one can delete most of the content in the docs folder except **source** folder and **index.html** and redo step 4.

(6) Push the local changes to the **hextof-processor** repository. If necessary, use force at the end.

.. code-block:: bash

   git push origin master -f


This can eliminate some of the unnecessary conflicts from the various javascript, CSS files generated in the rebuilding process.