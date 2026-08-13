# -*- coding: utf-8 -*-
TITLE = "What is an IPL trade actually worth?"
BY    = "Omkar Walunj"

B = [
('t', """An IPL trade can change the trajectory of multiple teams with a single decision. Yet we still don’t have a proper way to price the trade itself. We know what teams paid for them at the auction.

"""),

('h', "How IPL Trade Values Works?"),
('t', """Example, If Mumbai Indians send a player to Chennai Super Kings, what has Chennai really received?

To value a trade, we need to answer four questions:

**What is the player worth?**  **What is he worth to this particular team?**  **What can the team realistically recover if he leaves?**  **And is making the trade better than keeping him?**

IPL Trade Values answers these questions through five connected components:

**Player Valuation → Team Fit → Replacement & Auction → Trade Economics → Counterfactual Simulation**

The framework starts by putting every player on a common scale using **Projected WAR (pWAR)**, then asks how that value changes when the player is placed inside a specific squad. It then models the auction pool and competition for replacements, thus calculates the possible recoverability from the auction, prices the financial side of the transaction, and finally compares the team in two worlds: **one where the trade happens and one where it doesn't.**"""),

('h', "What the model has to solve?"),
('t', """Valuation: What’s a player’s intrinsic worth, isolated from the team context.

Projection: What is he likely to be worth next season and the one after that. This is much harder in a league as short and volatile as the IPL.

Team Fit: A player is never worth the same to every side. A team is basically twelve slots (once you factor in the impact player) and a set of constraints.

Replacement: When you trade a player away you go into an auction with a limited purse, competing against nine other teams for a pool of players that nobody knows during the time of trades.

Most of the arguments you see online are reasonable enough, but they almost always stop at the first problem."""),

('H', "1. What is a player worth?"),
('t', """The first step is putting players into the same unit.

I use **Runs Above Replacement**, converted into wins, to measure a player's contribution. The model starts at the ball level and estimates how much value was created relative to what would normally be expected from that match state.

**Run Expectancy**

For every ball, the model estimates the runs a team would be expected to score from the current over-and-wickets state.

A player's **Runs Created** is then based on the difference between the actual outcome and that expected outcome, with wickets valued through the change in run expectancy between the state before and after the wicket."""),
('i', 'wicket_value.png', 'With 120 balls left and nobody out, a wicket costs about 14 runs. In the last five overs it costs around 2.5.'),
('t', """A wicket does not have a fixed value. With 120 balls remaining and no wickets down, a wicket is worth about **14 runs** in the model. In the final five overs, that falls to roughly **2.5 runs**, because there are far fewer future runs left to lose.

**Context**

The contribution is then adjusted for the context in which it occurred.

The model accounts for:

- **Venue**
- **Leverage**
- **Innings**
- **Pace vs spin**
- **Batter handedness**

Batting and bowling contributions are also linked through the same run-based framework, so the value created by one side is the value conceded by the other.

**Replacement Level**

The next question is: *better than whom?*

I define replacement level as the contribution expected from a player who is realistically available to a franchise rather than an average IPL player.

The model establishes a league-level replacement pool using playing-time-weighted player participation, with the top eight batters and six bowlers from each team forming the regular-player pool. The players below that level establish the replacement benchmark.

**From Runs to WAR**

The resulting contribution is converted from runs into wins.

In the 2023–2026 data, approximately **5.9 runs correspond to one additional win per match**, or around **82.5 runs over a 14-match season**.

WAR is then expressed relative to replacement:

**Replacement = 0 WAR**

A regular player is around **1.5-2 WAR**, while the strongest players reach substantially higher values.

For players with limited IPL records, the same framework is also applied to T20I data and blended according to the precision of the available information. 

The resulting measure is **Projected WAR (pWAR)**: the model's estimate of what the player is expected to contribute in the upcoming season."""),

('H', "II. What is he worth to this team?"),
('t', """A player's WAR tells us what he is worth in isolation. It does **not** tell us what he is worth to a particular team. Let's take Dewald Brevis' case. His WAR comes out at 1.12, so now, if we ask what he'd be worth to Mumbai Indians? Answer is almost nothing, as MI already have Rickelton and Will Jacks, both of whom are ahead of him. Bringing Brevis in results in an option for a position that's already covered."""),
('i', 'brevis_four_teams.png', 'Illustration of the same player’s value changing across team contexts.'),
('t', """**Slots are not equal**

I treat a squad as a set of roles and slots rather than simply a collection of players. Different positions receive different amounts of exposure. An opener faces far more balls than a number eight, while a primary bowler contributes far more deliveries than a seventh bowling option.

Therefore, the same improvement in pWAR can have very different value depending on **where the improvement occurs**. This exposure is combined with the estimated importance of each batting position and bowling phase when evaluating the team's needs."""),
('i', 'slot_exposure.png', 'Seasonal exposure across batting positions and bowling options, illustrating why the same pWAR improvement can have different team value.'),
('t', """Thus, I built a **team-selection optimizer**. For every player, I mapped the role he can realistically perform. It respects the overseas limit, batting positions and bowling-phase coverage, and finds the best legal XII for each squad.

So, a hole is not only just a player leaving, but also a slot where the best replacement player you have left is below what that position should deliver (calculated from the league average requirement for each role).

After we know this, the intuitive next step was to find: **What the team actually loses when a player leaves and how likely will the team recover that loss in the mini auction.**"""),

('H', "III. Can you just buy a replacement?"),
('t', """The trade window shuts before the release deadline, which shuts before the auction, so at the moment you're deciding, you don't know which players will even be available.

I had to predict that pool in order to solve this problem. I trained a model on the 2023 to 2026 transitions using salary, share of matches played, performance against the average for that specific role, and squad depth in front of the player.

The model outputs a probability for every contracted player. I set the cutoff separately for each role and nationality, choosing the probability that reproduces that group's own historical release rate. That produces the release list.

Hardik Pandya's release probability lands at 0.78, which is worth noting given the trade talk, because it says Mumbai were probably moving on either way. At the other end, Sooryavanshi sits at 0.004 and Sai Sudharsan at 0.006 meaning nobody is releasing those two. (Performance of last 4 years was used and regression to the mean was done for players with lower sample size). Adding these released players to those who went unsold at the last auction, gives me the auction pool.

For the auction itself I ran it as a sequential thing. First, I asked what kind of player the vacancy in that team actually needs. Each team bids what the player is worth to its remaining holes, and walks away when the price goes past that.

**Willingness to pay:** For any player, a team's ceiling is the improvement he makes to their best legal XII, converted into money. KKR's opening slot is worth 290 balls a season. If the man currently filling it sits at 0.18 pWAR and a 0.30 pWAR opener replaces him, that's 0.42 wins."""),
('f', r"(0.30-0.18)\times 290 \div 82.5 = 0.42"),
('t', """I regressed what teams actually paid at the 2023, 2024, and 2026 auctions against what each player projected to be worth before that auction, which gives me the price:"""),
('f', r"\text{price} = ₹4.48\ \text{crore} + ₹6.61\ \text{crore} \times \text{projected wins}"),
('t', """So Kolkata's ceiling for that opener works out near **₹7 crore**, and above that they're overpaying, for that **0.75 pWAR** gain.

**Which gives you a demand curve:** Sweep the quality of the player from bad to excellent and record what each team would pay at each level. Punjab won't pay a rupee for an opener until quality passes pWAR of the current openers, because their incumbent is already better than that. Kolkata start bidding at 0.18 pWAR because they have a genuine hole."""),
('i', 'demand_curve.png', 'Team-specific willingness-to-pay curves across player quality levels.'),
('t', """Also, every bid prevents something else, so the bidding has to account for what the money would otherwise buy.

However, in an Auction, Chennai isn't the only team bidding.

Even if I expect five suitable players to enter the auction, that doesn't mean CSK gets one of them. Another team may need the same role more badly, have more money, or simply decide to spend more. So, I calculated: What is the probability that CSK can actually acquire someone at least as good as Brevis?"""),
('i', 'replacement_odds.png', 'Probability of filling a vacancy versus probability of replacing the quality of the player lost.'),
('t', """For the sake of understanding this effect- for one of the vacancies, the model gave that team an 82.5% chance of filling the role, but only a 9.7% chance of finding someone at least as good as the player it lost.

So this process gives us a probability distribution over what the team is likely to get back, i.e. the recovery value of the vacancy.

After getting the recovery likelihood, the major aspect I studied was money, opportunity cost and the value of the trade itself."""),

('H', "IV. Putting a price on Trades"),
('t', """In Football or Baseball you buy a player and you can keep him for years. In IPL, due to a 3-year cycle the upcoming 2027 is the last season of the current cycle. 

**Surplus value:** (What he's worth - what he costs) summed over every year you hold him."""),
('f', r"\text{Surplus} = (\text{market-fair price} - \text{salary}) + \text{retention option value}"),
('t', """The first bracket is the guaranteed 2027 season. Market-fair price is the ₹4.48 + ₹6.61 × pWAR equation which I showed in the last segment, so for a player projecting 0.39 wins that's about ₹5.7 crore.

The second term is 2028 onward, and obviously it only exists if you retain him. So, it's only worth something when his projected value clears the slab price:"""),
('f', r"\text{option} = \sum \max(0,\ \text{value}_t - \text{slab price}) \times \text{discount}^{\,t}"),
('t', """where value_t is his value in the year 't' and slab price is at least ₹11 crore for a capped player and ₹4 crore for an uncapped one.

Hardik's surplus value due to 3 very poor IPL seasons comes out at -₹10.6 crore. He projects at 0.39 wins/season, so market-fair is about ₹5.9 crore, and he's on ₹16.35 crore salary. Rishabh Pant on ₹27 crore comes out at −₹19 crore. Ayush Mhatre at ₹30 lakh comes out at +₹7.5 crore. (These are market-fair values in isolation; they don't account for auction dynamics or competition for the player)

**The rupee has an opportunity cost.**

If I spend ₹10 crore acquiring one player, that ₹10 crore isn't available for the other vacancies in my squad. So the financial calculation feeds back into the auction model through **opportunity cost**.

So the trade is evaluated using:

**Player value + team fit + replacement value + financial surplus − opportunity cost**"""),

('H', "V. Does the team actually end up better off?"),
('t', """So now we've got something substantial- there's a value, a price, and a probability of recovery. The last thing left is to actually run the season and see what changes wrt States S1 and S2 as they're 2 different states of the same team based on the decision they took in the trade.

**S1: No trade** so the player(s) stays. The team goes into the release process with its original squad, builds its purse, enters the auction and fills whatever vacancies it has.

**S2: Trade.** The trade happens first which in turn changes the squad, the salaries and the vacancies. The release decisions are then applied to that new state, the purse changes accordingly, and the team enters the auction with a different set of needs.

**Season Simulation**

Then I simulated the season 2000 times for both states, and predicted the Win%, Playoff probability, Title Probability.

The simulation produces distributions for:

- **Regular-season win percentage**
- **Playoff probability**
- **Title probability**
- **Final squad/XII value**
- **Asset value**

The trade's effect is then measured as the difference between the two states:

**Δ = S2 − S1**

So, for example:

**Δ Playoff Probability = P(Playoffs | S2) − P(Playoffs | S1)** and similarly for the other outcomes.

**Trade Utility**

The final trade utility therefore asks a counterfactual question:

> **Is the team better off after making the trade than it would have been if the trade had never happened?**

That is the final output of the framework.

**The trade that already happened**

Pant to Delhi, Kuldeep to Lucknow."""),
('i', 'pant_kuldeep.png', 'The Rishabh Pant–Kuldeep Yadav trade evaluated through the counterfactual framework.'),
('t', """Lucknow gained nine points of playoff probability by giving up their captain. Pant on ₹27 crore was costing them more than he was returning, and shedding that contract freed up a squad they could actually build in the auction. Delhi barely moved either way meaning their playoff probability won't change much by this trade.

Now, here's how the three versions of the Hardik Pandya trade look like:"""),
('i', 'hardik_three.png', 'Three evaluated versions of the Hardik Pandya trade and their simulated outcomes.'),
('t', """For CSK that's a spread of four percentage points of title probability and it's decided entirely by which second name goes to MI. Mhatre alone is worth more than twice what Khaleel is worth in this deal and that only shows up because Mhatre's surplus value is way more than Khaleel's and most likely he'll remain uncapped till the next mega auction. So, don't give up Mhatre. Also, push Hardik's salary down. But the reality is he doesn't fix what's actually wrong for them.

Mumbai improves in all three cases, which shows they would be the happier of the 2 sides. Interestingly, MI has more odds of reaching playoffs in the 2nd case than the 3rd which makes sense because they need a player of Khaleel's attributes way more than that of Brevis.

The point is that the model can now answer: Given everything I know before the auction, how much better or worse does making this trade leave the team?

Such a framework would make the judgement of the decision-makers more informed. There will always be flaws with the model, but that's something which will get lesser with more use and feedback.

All I care is that if I can quantify what is being given up and show what has to be true for a trade to work, then I think I have got closer to answering the question I started with:

**What is an IPL trade actually worth?**"""),
]
