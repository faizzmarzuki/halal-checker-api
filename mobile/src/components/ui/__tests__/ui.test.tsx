import React from "react";
import { render, fireEvent } from "@testing-library/react-native";
import { Button } from "../Button";
import { Input } from "../Input";

test("Button renders its title and fires onPress", () => {
  const onPress = jest.fn();
  const { getByText } = render(<Button testID="b" title="Tap me" onPress={onPress} />);
  fireEvent.press(getByText("Tap me"));
  expect(onPress).toHaveBeenCalled();
});

test("Button is disabled while loading", () => {
  const onPress = jest.fn();
  const { getByTestId } = render(<Button testID="b" title="Go" onPress={onPress} loading />);
  fireEvent.press(getByTestId("b"));
  expect(onPress).not.toHaveBeenCalled();
});

test("Input shows label and error and forwards changes", () => {
  const onChangeText = jest.fn();
  const { getByText, getByTestId } = render(
    <Input testID="in" label="Email" error="Bad" value="" onChangeText={onChangeText} />,
  );
  expect(getByText("Email")).toBeTruthy();
  expect(getByText("Bad")).toBeTruthy();
  fireEvent.changeText(getByTestId("in"), "x");
  expect(onChangeText).toHaveBeenCalledWith("x");
});
