# -*- coding: utf-8 -*-
TITLE = "What is an IPL trade actually worth?"
BY    = "Omkar Walunj"
CRED  = ("Biotechnology and Artificial Intelligence at IIT Kharagpur | Cricket Analytics and Strategy "
         "Researcher | Presented at the ASA Sports Analytics Conference 2026 | Winner of Dream11 "
         "Gameathon 2.0")
DATE  = "August 9, 2026"

B = [
('t', """We're pretty good at measuring performance these days. Expected runs, player impact models, win probability added. Plenty of numbers that tell us how much a player contributes on the field. We also know what teams paid for them at the auction. What we still don't have is a proper way to price the transaction itself.

A trade is a bit different. Example, If Mumbai Indians send a player to Chennai Super Kings, what has Chennai really received?

To judge a trade properly you need four things: What the player is worth, What he costs, How long you can keep him, and What you would have done instead. Those questions turn out to be surprisingly hard in the IPL. Fourteen matches a season and three-year cycles make everything noisier and more constrained than it looks.

I spent the last two weeks building a model that tries to tackle them. It ended up breaking into five segments: valuing the player, understanding the team's needs, finding the replacement, pricing the deal, and then checking whether the trade actually leaves the team better off.

A quick note on that last part. The example trades are just examples. If you jump straight to the end to see whether the model likes or hates a particular swap, you'll get a yes or no, but you'll miss the useful bit. The useful bit is that a trade is really four separate problems, and three of them have almost nothing to do with how good the players are."""),

('h', "What the model has to solve?"),
('t', """**Valuation:** What's a player's intrinsic worth, isolated from the team context.

**Projection:** What is he likely to be worth next season and the one after that. This is much harder in a league as short and volatile as the IPL.

**Team Fit:** A player is never worth the same to every side. A team is basically twelve slots (once you factor in the impact player) and a set of constraints.

**Replacement:** When you trade a player away you go into an auction with a limited purse, competing against nine other teams for a pool of players that nobody knows during the time of trades.

Most of the arguments you see online are reasonable enough, but they almost always stop at the first problem."""),

('H', "(I) What is a player worth?"),
('t', """Firstly, we need to put players in the same units, because there are number of roles and each comes with its own context. What I've used is runs above replacement, converted into wins.

For every ball a batter faces, I calculated how many runs a replacement level player would have scored in that same situation, batting in that same position, against that type of bowling. Subtract the replacement player's values from the observed values of the player under consideration. I Did the same on the bowling side, but before that I categorised bowlers by their phase usage and bowling style. Adding the two halves together gives you player's contribution in runs. Divide by the number of runs it takes to win a match in the IPL and you have it in wins. This is essentially Wins Above Replacement (WAR).

Each of those steps has intricacies worth understanding. So, before I move on, let's discuss those first.

**A wicket is not worth a fixed number of runs:** I fitted run expectancy across the 2023 to 2026 seasons, which gives you the average runs a team still scores from any given position. The value of a wicket is then just the gap between the state before and the state after. At any fixed point in the innings, a wicket costs more when more have already fallen, because you're pulling the tail closer."""),
('i', 'wicket_value.png',
 'With 120 balls left and nobody out, a wicket costs about 14 runs. In the last five overs it costs around 2.5.'),
('t', """**Runs are not worth the same at every ground:** Over a season the venues a player happens to visit can shift his numbers by a few percent in either direction. So every ball is adjusted by a venue factor before it counts.

**How many runs is a win?** The answer is about 5.9 runs per match, or 82.5 runs across a 14 game season.

So this means that if you improve your team by six runs a match, all season, you will win one extra game. In the 2023 to 2026 data, about one loss in six was by six runs or fewer.

**Who is the replacement?** I've defined "Replacement level" as the standard you'd get from a player who is freely available. A franchise watches its players every day in the nets and then decides who to pick. Hence, I sorted every player by the share of his team's matches he actually played, and performance tracks it almost perfectly. Players picked in more than 80% of games strike at 154. Between 60% and 80%, 145. Below 15%, 106."""),
('i', 'replacement.png', ''),
('t', """I found that the Replacement level in the IPL turns out to sit around the player selected in roughly 47% of his team's games. Also, it's worth mentioning that the replacement level depends on the role and it also depends on nationality, because an Indian leaving has to be replaced by an Indian, while an overseas player can be replaced by either.

**Putting it on a readable scale**

The final step is a rescaling that sets a league average regular at 1.00. On that scale, the top of the league sits between two and three. A regular player sits near one. Surprisingly plenty of contracted players are below half. Thus, we get the WAR for each player.

Using the player's WAR I can potentially calculate: What should I expect this player to contribute if I put him on the field next season? This is the Projected WAR (pWAR)

But it still wasn't enough to evaluate a trade. Because the way MI sees a player vs what CSK sees in that same player can differ. What we just found is the isolated worth of the player, now let's bring the element of the team to this."""),

('H', "(II) What is he worth to this team?"),
('t', """Let's take Dewald Brevis' case. His WAR comes out at 1.01, so slightly above a league average regular. Now if we ask what he'd be worth to Mumbai Indians? Answer is almost nothing, and it has nothing to do with how good he is. Mumbai already have Rickelton and Will Jacks, both of whom are ahead of him. Bringing Brevis in results in an option for a position that's already covered. What I mean is he wouldn't get picked (Also, Sherfane is already there with the team)"""),
('i', 'brevis_four_teams.png', ''),
('t', """To handle that I had to start thinking about squads as a set of N slots.

**Slots aren't equal:** An opener faces around 290 balls across a season, number three gets 255, number eight gets 57. On the bowling side the first five options bowl roughly 270 to 290 balls each, the sixth bowler about 165, the seventh barely 25.

This means a +0.10 Projected WAR (pWAR) improvement at the top of the order is worth five times the same improvement at number eight, purely because of how many balls pass through each position which is 'Exposure', a property of each role. It's also why the impact player rule matters more because it isn't just an extra batter, it's also about an extra 165 balls of bowling you no longer need from your sixth option."""),
('i', 'slot_exposure.png', ''),
('t', """The same thing happens with bowling. If a team already has 2 Powerplay seamers covering the powerplay, another powerplay seamer in the XI isn't necessarily solving much. A bowler who can give you a few overs at the death will be worth more to that particular team.

Thus, I built a team-selection optimiser. For every player, I mapped the role he can realistically perform. It respects the overseas limit, batting positions and bowling-phase coverage, and finds the best legal XII for each squad.

This sort of explains why someone like Hardik Pandya is particularly interesting. His value isn't simply his batting WAR plus his bowling WAR. The fact that he can occupy a number of batting positions and provide overs changes the number of ways a team can construct its XII.

So a hole is not only just a player leaving, but also a slot where the best replacement player you have left is below what that position should deliver (calculated from the league average requirement for each role).

So now I knew what a player is worth, and what a hole is worth. After this, the intuitive next step was to find: What the team actually loses when he leaves and how likely will the team recover that loss in the mini auction."""),

('H', "(III) Can you just buy a replacement?"),
('t', """Turns out, it's a bit complicated. The trade window shuts before the release deadline, which shuts before the auction, so at the moment you're deciding, you don't know which players will even be available.

I had to predict that pool in order to solve this problem. I trained a model on the 2023 to 2026 transitions using salary, share of matches played, performance against the average for that specific role, and squad depth in front of the player. It gets an AUC of 0.766 out of sample, which is decent. The strongest predictor was the selection. If a team keeps picking you, you tend to stay, regardless of how the numbers look. Being overseas is the only feature that pushes the player at a disadvantage, which makes sense given only four can play.

The model outputs a probability for every contracted player, so the next question is where to apply the threshold. I set the cutoff separately for each role and nationality, choosing the probability that reproduces that group's own historical release rate. That produces the release list.

Hardik Pandya's release probability lands at 0.78, which is worth noting given the trade talk, because it says Mumbai were probably moving on either way. At the other end, Sooryavanshi sits at 0.004 and Sai Sudharsan at 0.006 meaning nobody is releasing those two. (Performance of last 4 years was used and regression to the mean was done for players with lower sample size). Adding these released players to those who went unsold at the last auction, gives me the auction pool.

Once you know who's released, you can work out the purse. A team starts with whatever was left over from the last auction, adds the ₹6 crore the BCCI gives everyone, then the trade happens, and then the release deadline. This order kind of matters here, you'll definitely get that later.

For the auction itself I ran it as a sequential thing. First I asked what kind of player the vacancy in that team actually needs. Each team bids what the player is worth to its remaining holes, and walks away when the price goes past that. Prices come from a model fitted on the 2024 and 2026 auctions, which reproduces the two things real mini auctions do, about 65% of players going at base price and a handful going for absurd amount of money.

Each team needs to know what it would pay for what.

**Willingness to pay:** For any player, a team's ceiling is the improvement he makes to their best legal XII, converted into money. KKR's opening slot is worth 290 balls a season. If the man currently filling it sits at 0.18 pWAR and a 0.30 pWAR opener replaces him, that's 0.42 wins."""),
('f', r"(0.30-0.18)\times 290 \div 82.5 = 0.42"),
('t', """I regressed what teams actually paid at the 2023, 2024, and 2026 auctions against what each player projected to be worth before that auction, which gives me the price:"""),
('f', r"\text{price} = ₹4.48\ \text{crore} + ₹6.61\ \text{crore} \times \text{projected wins}"),
('t', """So Kolkata's ceiling for that opener is:"""),
('f', r"4.48 + (0.42 \times 6.61) \approx ₹7.3\ \text{crore}"),
('t', """Above that they're overpaying for those attributes.

**Which gives you a demand curve:** Sweep the quality of the player from bad to excellent and record what each team would pay at each level. Punjab won't pay a rupee for an opener until quality passes pWAR of the current openers, because their incumbent is already better than that. Kolkata start bidding at 0.18 pWAR because they have a genuine hole."""),
('i', 'demand_curve.png', ''),
('t', """Also, every bid prevents something else, so the bidding has to account for what the money would otherwise buy.

However, in an Auction, Chennai isn't the only team bidding.

Even if I expect five suitable players to enter the auction, that doesn't mean CSK gets one of them. Another team may need the same role more badly, have more money, or simply decide to spend more. So, I calculated: What is the probability that CSK can actually acquire someone at least as good as Brevis?"""),
('i', 'replacement_odds.png', ''),
('t', """For the sake of understanding this effect- for one of the vacancies, the model gave that team an 82.5% chance of filling the role, but only a 9.7% chance of finding someone at least as good as the player it lost.

So this process gives us a probability distribution over what the team is likely to get back, i.e. the recovery value of the vacancy.

After getting the recovery likelihood, the major aspect I studied was money, opportunity cost and the value of the trade itself."""),

('H', "(IV) Putting a price on Trades"),
('t', """In Football or Baseball you buy a player and you can keep him for years. In IPL, due to a 3-year cycle the upcoming 2027 is the last season of the current cycle. After that the mega auction occurs and teams have to start again. So whoever gets Hardik Pandya isn't buying an asset, they're effectively renting him for one season, with an option to retain him at a fixed slab price afterwards: ₹18, 14 and 11 crore for capped players and ₹4 crore for uncapped. Hence, an uncapped Indian who's already good is such a strange asset as he's the only kind of player you can keep cheaply.

**Surplus value:** (What he's worth - what he costs) summed over every year you hold him."""),
('f', r"\text{Surplus} = (\text{market-fair price} - \text{salary}) + \text{retention option value}"),
('t', """The first bracket is the guaranteed 2027 season. Market-fair price is the ₹4.48 + ₹6.61 × pWAR equation which I showed in the last segment, so for a player projecting 0.39 wins that's about ₹5.7 crore.

The second term is 2028 onward, and obviously it only exists if you retain him. So it's only worth something when his projected value clears the slab price:"""),
('f', r"\text{option} = \sum \max(0,\ \text{value}_t - \text{slab price}) \times \text{discount}^{\,t}"),
('t', """where value_t is his value in the year 't' and slab price is at least ₹11 crore for a capped player and ₹4 crore for an uncapped one.

Hardik's surplus value due to 3 very poor IPL seasons comes out at -₹10.6 crore. He projects at 0.39 wins/season, so market-fair is about ₹5.9 crore, and he's on ₹16.35 crore salary. Rishabh Pant on ₹27 crore comes out at −₹19 crore. Ayush Mhatre at ₹30 lakh comes out at +₹7.5 crore. (These are market-fair values in isolation; they don't account for auction dynamics or competition for the player)

**The rupee has an opportunity cost.**

If I spend ₹10 crore acquiring one player, that ₹10 crore isn't available for the other vacancies in my squad. So the financial calculation feeds back into the auction model.

So now we've got something substantial- there's a value, a price, and a probability of recovery. The last thing left is to actually run the season and see what changes wrt States S1 and S2 as they're 2 different states of the same team based on the decision they took in the trade. (S1: No trade occured, this serves like a 'control' and S2: Given the trade happened, what changed in the team's holes and how team's auction plan changed and finally how did the team fare in the league)"""),

('H', "(V) Does the team actually end up better off?"),
('t', """As I stated about the '2 unique states' of the team above, I treated the trade as two different worlds.

**S1: No trade** so the player(s) stays. The team goes into the release process with its original squad, builds its purse, enters the auction and fills whatever vacancies it has.

**S2: Trade.** The trade happens first which in turn changes the squad, the salaries and the vacancies. The release decisions are then applied to that new state, the purse changes accordingly, and the team enters the auction with a different set of needs.

Then I simulated the season 2000 times for both states, and predicted the Win%, Playoff probability, Title Probability.

**The trade that already happened**

Pant to Delhi, Kuldeep to Lucknow."""),
('i', 'pant_kuldeep.png', ''),
('t', """Lucknow gained nine points of playoff probability by giving up their captain. Pant on ₹27 crore was costing them more than he was returning, and shedding that contract freed up a squad they could actually build in the auction. Delhi barely moved either way meaning their playoff probability won't change much by this trade.

Now, I won't bore you more with this stuff, here's what you've been waiting for this long to see: how the three versions of the Hardik Pandya trade look like:"""),
('i', 'hardik_three.png', ''),
('t', """For CSK that's a spread of four percentage points of title probability and it's decided entirely by which second name goes to MI. Mhatre alone is worth more than twice what Khaleel is worth in this deal and that only shows up because Mhatre's surplus value is way more than Khaleel's and most likely he'll remain uncapped till the next mega auction. So, don't give up Mhatre. Also, push Hardik's salary down. But the reality is he doesn't fix what's actually wrong for them.

Mumbai improves in all three cases, which shows they would be the happier of the 2 sides. Interestingly, MI has more odds of reaching playoffs in the 2nd case than the 3rd which makes sense because they need a player of Khaleel's attributes way more than that of Brevis.

The point is that the model can now answer: Given everything I know before the auction, how much better or worse does making this trade leave the team?

Such a framework would make the judgement of the decision-makers more informed. There will always be flaws with the model, but that's something which will get lesser with more use and feedback.

All I care is that if I can quantify what is being given up and show what has to be true for a trade to work, then I think I have got closer to answering the question I started with:

**What is an IPL trade actually worth?**"""),
]
