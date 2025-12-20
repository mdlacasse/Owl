# Website source

This folder contains the source code for the website hosted at [https://mdlacasse.github.io/OWL/](https://mdlacasse.github.io/OWL/).

The website is built using [Quarto](https://quarto.org/) and hosted using GitHub Pages.

## Building the website locally

To build the website locally, you need to have [Quarto](https://quarto.org/docs/get-started/) installed on your machine.


1. Open a terminal and navigate to the `site-src/` directory.
2. Run the following command to render the website:

   ```bash
   quarto render
   ```

3. After rendering, the generated website files will be located in the `../docs` directory. This directory is configured to be the source for GitHub Pages.
