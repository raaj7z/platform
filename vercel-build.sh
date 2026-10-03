#!/bin/bash
set -e

rm -rf vendor

mkdir -p vendor

git clone --depth 1 https://github.com/raaj7z/DarkWeb-Deanonymization.git vendor/DarkWeb-Deanonymization
git clone --depth 1 https://github.com/raaj7z/osint-engine.git vendor/osint-engine
git clone --depth 1 https://github.com/raaj7z/Persona.git vendor/Persona
