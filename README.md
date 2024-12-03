# visualize_advent_of_code_private_leaderboard

This is a system to generate HTML files with [Advent of Code](https://adventofcode.com/)'s private leaderboard data.

For convenience of use, this system is wrapped in Docker image.

To use this system you need JSON files (or just one file) with private leaderboard info.
You can download that files in any way you like, for example
you can use https://github.com/bessarabov/save_advent_of_code_private_leaderboard_json

You need the JSON files to be places in some directory with the years as names.

Here is the example (you don't need to have the files for all years, the
system will generate HTML for one or more JSON files):

```
input/
├── 2015.json
├── 2016.json
├── 2017.json
├── 2018.json
├── 2019.json
├── 2020.json
├── 2021.json
├── 2022.json
└── 2023.json
```

Next you need to create a directory to store generated HTML files:

```
$ mkdir output/
```

After that, run the docker command:

```
$ docker run \
    --rm \
    -v `pwd`/input/:/input/ \
    -v `pwd`/output/:/output/ \
    bessarabov/visualize_advent_of_code_private_leaderboard:1.1.1 \
    ;
```
