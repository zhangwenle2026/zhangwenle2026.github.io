import json, re

# G2P-ish mapping: English letters/letter-groups -> Chinese char approximations (拼音读感)
# Focus on the sounds a Chinese learner needs; keep it readable, one hanzi per sound unit.
MAP = [
    ("tion", "申"), ("sion", "申"), ("ough", "欧"), ("augh", "阿"),
    ("ch", "吃"), ("sh", "诗"), ("th", "斯"), ("ph", "夫"), ("wh", "乌"),
    ("ck", "克"), ("ng", "嗯"), ("qu", "奎"), ("gh", "格"),
    ("ai", "艾"), ("ay", "艾"), ("ea", "伊"), ("ee", "伊"), ("ei", "艾"), ("ey", "艾"),
    ("oa", "欧"), ("ow", "欧"), ("oi", "奥伊"), ("oy", "奥伊"), ("oo", "乌"),
    ("au", "奥"), ("aw", "奥"), ("ew", "尤"), ("ui", "威"), ("ue", "乌"),
    ("ou", "奥"), ("ie", "伊"), ("igh", "艾"),
    ("a", "阿"), ("e", "额"), ("i", "伊"), ("o", "欧"), ("u", "阿"),
    ("b", "布"), ("c", "克"), ("d", "德"), ("f", "夫"), ("g", "格"),
    ("h", "喝"), ("j", "杰"), ("k", "克"), ("l", "勒"), ("m", "姆"), ("n", "恩"),
    ("p", "普"), ("q", "克"), ("r", "儿"), ("s", "丝"), ("t", "特"), ("v", "维"),
    ("w", "乌"), ("x", "克斯"), ("y", "伊"), ("z", "兹"),
]

def word_xy(word):
    w = word.lower()
    out = ""
    i = 0
    while i < len(w):
        for pat, s in MAP:
            if w.startswith(pat, i):
                out += s
                i += len(pat)
                break
        else:
            i += 1  # skip unknown chars (punct, digits)
    if not out:
        return None
    return out

def sentence_xy(sent):
    words = re.findall(r"[A-Za-z][A-Za-z'\-]*", sent)
    pieces = []
    for w in words:
        if len(w) <= 2:
            pieces.append(word_xy(w) or "")
        else:
            pieces.append(word_xy(w) or "")
    # join words with spaces to keep readability
    return " ".join(p for p in pieces if p)

def main():
    with open('translated.json') as f:
        blocks = json.load(f)
    out = []
    for b in blocks:
        sents = re.split(r'(?<=[.?!…])\s+', b['text'].strip())
        sents = [s for s in sents if s.strip()]
        xy_list = [sentence_xy(s) for s in sents]
        # distribute block cn to first sentence if only one sentence; else put cn at block level
        item = dict(b)
        item['sentences'] = sents
        item['xy'] = xy_list
        if len(sents) == 1:
            item['cnSentence'] = [b.get('cn','')]
        else:
            item['cnSentence'] = []
        out.append(item)
    with open('final_data.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    print('blocks:', len(out))

if __name__ == '__main__':
    main()
