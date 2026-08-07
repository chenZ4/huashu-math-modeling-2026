CXX = g++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
BUILD = bin
SRC = src

all: $(BUILD)/main

$(BUILD)/main: $(SRC)/main.cpp $(SRC)/floor_plan.hpp
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $(SRC)/main.cpp

test: $(BUILD)/test_main
	./$(BUILD)/test_main

$(BUILD)/test_main: $(SRC)/test_main.cpp $(SRC)/floor_plan.hpp
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -DTREE_DEBUG -o $@ $(SRC)/test_main.cpp

clean:
	rm -rf $(BUILD)

.PHONY: all test clean
