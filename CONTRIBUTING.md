# Contributing to Orkes

First off, thank you for considering contributing to Orkes! It's people like you that make Orkes such a great tool.

## Where do I go from here?

If you've noticed a bug or have a feature request, [make one](https://github.com/hfahrudin/orkes/issues/new)! It's generally best if you get confirmation of your bug or approval for your feature request this way before starting to code.

### Reporting Bugs

When reporting a bug, please include the following:

*   A clear and descriptive title.
*   A step-by-step description of how to reproduce the bug.
*   The expected behavior and what actually happened.
*   The version of Orkes you are using.
*   Any relevant code snippets, screenshots, or error messages.

### Suggesting Enhancements

When suggesting an enhancement, please include the following:

*   A clear and descriptive title.
*   A detailed description of the proposed enhancement.
*   The problem that the enhancement solves.
*   Any alternative solutions or features you've considered.

## Fork & create a branch

If this is something you think you can fix, then [fork Orkes](https://github.com/hfahrudin/orkes/fork) and create a branch with a descriptive name.

A good branch name would be (where issue #325 is the ticket you're working on):

```sh
git checkout -b 325-add-japanese-translations
```

## Get the code

```sh
git clone https://github.com/<your-username>/orkes.git
cd orkes
```

## Set up the development environment

We use a `virtualenv` to manage dependencies. To set it up, run:

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirement.txt
```

## Run the tests

To run the tests, run:

```sh
pytest
```

## Make your changes

Make your changes to the code. Please make sure to follow the existing coding style.

## Commit your changes

Commit your changes with a clear and descriptive commit message.

```sh
git commit -m "feat: Add Japanese translations"
```

## Push your changes

Push your changes to your fork.

```sh
git push origin 325-add-japanese-translations
```

## Submit a pull request

[Submit a pull request](https://github.com/hfahrudin/orkes/compare) to the `main` branch.

Please include the following in your pull request:

*   A clear and descriptive title.
*   A summary of the changes you've made.
*   The issue number that your pull request resolves.

## Code of Conduct

By contributing to Orkes, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
