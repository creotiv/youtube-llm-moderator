#!/usr/bin/env python3
import argparse
import sys

def parse_history_line(line):
    """
    Parses a history line of form:
      'LABEL' , for message: 'TEXT'
      or
      'FAIL','LABEL' , for message: 'TEXT'
    Returns: (text, predicted_orig, was_fail:bool)
    """
    parts = line.strip()
    if not parts:
        return None

    try:
        left, right = parts.split(", for message:", 1)
    except ValueError:
        raise ValueError(f"Bad format in history line: {line!r}")

    text = right.strip()
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]
    else:
        raise ValueError(f"Cannot parse comment text from: {right!r}")

    was_fail = False
    if "FAIL" in left:
        was_fail = True

    predicted_orig = "DELETE"
    if "KEEP" in left:
        predicted_orig = "KEEP"

    return text, predicted_orig.upper(), was_fail


def parse_pred_line(line):
    """
    Parses a prediction line of form:
      'LABEL', 'TEXT'
    Returns: (text, predicted_new)
    """
    parts = [p.strip() for p in line.strip().split(",", 1)]
    if len(parts) != 2:
        raise ValueError(f"Bad format in pred line: {line!r}")
    lbl = parts[0].strip("'\"").upper()
    text = parts[1].strip()
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]
    return text, lbl

def verify(train, pred):

    truth = {}
    was_fail_map = {}
    with open(train, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            text, orig_lbl, was_fail = parse_history_line(ln)
            if was_fail:
                was_fail_map[text] = orig_lbl
            else:
                truth[text] = orig_lbl
    
    total = 0
    new_pred = {}
    with open(pred, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            text, lbl = parse_pred_line(ln)
            new_pred[text] = lbl
        total = len(new_pred)

    correct = fail_total = fail_corrected = 0
    tp = fp = fn = tn = 0

    for comment, pred in new_pred.items():
        fail = False
        lbl = truth.get(comment)
        if not lbl:
            fail = True
            lbl = was_fail_map.get(comment)
        if lbl is None:
            print(f"[WARN] No history record for: {comment!r}", file=sys.stderr)
            continue


        if pred == lbl and not fail:
            correct += 1
            if pred == "DELETE":
                tn += 1
            else:
                tp += 1
        elif pred != lbl and fail:
            correct += 1
            fail_corrected += 1
            if pred == "DELETE":
                tn += 1
            else:
                tp += 1
        elif pred == lbl and fail:
            fail_total += 1
            if pred == "DELETE":
                fn += 1
            else:
                fp += 1
        elif pred != lbl and not fail:
            fail_total += 1
            if pred == "DELETE":
                fn += 1
            else:
                fp += 1
        else:
            print("FUKC")
            

    incorrect = total - correct
    overall_acc = correct / total * 100 if total else 0.0
    fail_fix_rate = (fail_corrected / len(was_fail_map) * 100) if fail_total else 0.0

    print(f"Total comments evaluated: {total}")
    print(f"Overall accuracy:       {overall_acc:.2f}%  ({correct}/{total})")
    print(f"Incorrect predictions:  {incorrect}  ({incorrect/total*100:.2f}% of total)")
    print(f"Originally-FAIL cases:   {len(was_fail_map)}")
    print(f"FAIL cases corrected:    {fail_corrected}  ({fail_fix_rate:.2f}% of FAILs)")

    print(f"True Positive: {tp}")
    print(f"True Negative: {tn}")
    print(f"False Positive: {fp}")
    print(f"False Negative: {fn}")

    return {
        "accuracy": overall_acc,
        "true_positive":tp,
        "true_negative":tn,
        "false_positive":fp,
        "false_negative":fn,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verify new moderator predictions against historical data."
    )
    parser.add_argument("--history", required=True,
                        help="Path to history file with 'FAIL','LABEL', for message: '…'")
    parser.add_argument("--preds", required=True,
                        help="Path to new predictions file (output of test script).")
    args = parser.parse_args()

    res = verify(args.history, args.preds)
    print(res)

if __name__ == "__main__":
    main()
