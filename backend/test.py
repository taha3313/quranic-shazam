from identify_reciter import identify_reciter

matches = identify_reciter("sample_input.wav")
for reciter, score in matches:
    print(f"{reciter}: {score:.4f}")
