During the session:  
    - Check the **term**:
        The user uses a word that does not match `README.md`.  
        Ask which meaning is right at once. 
        Example: "Your term says 'cancellation' means X. You seem to mean Y. Which one?"  
    - Make vague words clear:  
        The user uses a word with many meanings.  
        Offer one clear word.  
        Example: "You say 'account'. Do you mean the Customer or the User? They are different."  
    - Check the code and **ADR**:  
        The user says how something works.  
        Check if the code matches.  
        Raise the conflict at once.  
        Example: "Your code cancels the whole Order. You just said a partial cancel is possible. Which one is right?"  
    - Update the **term** and **ADR** at once.  

**term** Rules:  
    - Pick one word:  
        Many words name the same idea.  
        Pick the best word.  
        List the other words under `_Avoid_`.  
    - Keep the definition short:  
        Use one or two sentences.  
        Say what the term is.  
        Skip what the term does.  
    - Add only project terms:  
        Add a term only when it is special to this project.  
        Skip a general programming word.  
    - Group terms:  
        Terms form a clear group.  
        Put the group under a subheading.  
        All terms sit in one area.  
        Use one flat list.  

**ADR** Rules:
    - ADR is Architecture Decision Record.
    - A future reader looks at the code and asks why it works this way.  
    - You pick one option for a clear reason. A future reader will ask why you picked it.  

The user goes against a decision you already made.  

