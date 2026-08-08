CXX = g++
CXXFLAGS = -std=c++17 -O3 -Wall -Wextra
BUILD = bin
SRC = src
HDRS = $(SRC)/floor_plan.hpp $(SRC)/sa.hpp

all: $(BUILD)/main

$(BUILD)/main: $(SRC)/main.cpp $(HDRS)
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -o $@ $(SRC)/main.cpp

test: $(BUILD)/test_main
	./$(BUILD)/test_main

$(BUILD)/test_main: $(SRC)/test_main.cpp $(SRC)/test_oracle.hpp $(HDRS)
	@mkdir -p $(BUILD)
	$(CXX) $(CXXFLAGS) -DTREE_DEBUG -o $@ $(SRC)/test_main.cpp

test-san: $(BUILD)/test_main_san
	./$(BUILD)/test_main_san

$(BUILD)/test_main_san: $(SRC)/test_main.cpp $(SRC)/test_oracle.hpp $(HDRS)
	@mkdir -p $(BUILD)
	$(CXX) -std=c++17 -O1 -g -DTREE_DEBUG -fsanitize=address,undefined \
		-fno-omit-frame-pointer -o $@ $(SRC)/test_main.cpp

clean:
	rm -rf $(BUILD)

.PHONY: all test test-san clean
