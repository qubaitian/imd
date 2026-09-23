When you chat, reply, docs, code comments, git commits:  
    Use very **simple and easy** English.  
    Active voice. Present tense.  
    One word one meaning: same term for same thing.  
    One idea per sentence.  
    One sentence per line with two spaces.  
    When one sentence uses `when`, `if`, `unless`, or another condition:  
        Indent the next lines by 4 spaces.  
        Write the block like Python.  

Before implementation:  
    Find each **fact** yourself.  
    When a change is small and clear:  
        Change directly.  
    When the task needs an important design choice:  
        Start a design interview.  

During the interview:  
    Build a **design tree**:
        The **frontier** is the decisions ready for me to make.  
        Ask every frontier decision in one round.  
        Number each decision.  
        Give your recommended answer.  
        Use this format:  
            **Q1** - **<title>**: <question and choices>  
            <recommended answer>  
            ---  
            **Q2** - **<title>**: <question and choices>  
            <recommended answer>  
        Wait for my answers.  
        When I answer:  
            Update the design tree.  
            Find the next frontier.  
            Ask the next round.  
        When the tree is ready:
            Show it to me.
    Update **glossary** in `README.md`:  
        When I use a term with a different meaning from the glossary:  
            Ask which meaning is right at once.  
        When a term is unclear or has more than one meaning:  
            Suggest a clear term.  
            Ask me to confirm its meaning.  
        When we settle a term:  
            Record it at once.  
        Use one proper term for each idea.  
        List other names under `_Avoid_`.  
        Define each term in one sentences.  
        Leave out general programming terms.  
        Include only terms with a meaning specific to this project.  
        Keep implementation details outside the glossary.  
        Group terms that belong together.  
        Put a term that others depend on ahead.
    Update **ADR** in `README.md`:  
        **ADR** means Architecture Decision Record:
            A future reader needs context to understand the choice.  
            A clear reason supports this choice over other real options.  
        When we settle the decision:  
            Record the ADR at once.  
            State the context, choice, and reason in one to three sentences.  
