"""
Copyright (C) 2022 Tim Schumacher

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import functools
import re

__all__ = [
    "fill",
    "load",
]


def fill(name: str, context: dict[str, str]) -> str:
    def evaluate_replacement(match: re.Match) -> str:
        return context[match.group(1)]

    return re.sub(r"\{\{\s*(.*?)\s*\}\}", evaluate_replacement, load(name))


@functools.cache
def load(name: str) -> str:
    with open(f"template/{name}.tpl", "r") as file:
        return file.read()
