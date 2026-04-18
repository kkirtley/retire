Create scenario_loader.py
- load YAML
- parse with yaml.safe_load
- validate into RetirementScenario
return clean validation errors
Create test_schema_validation.py
- baseline YAML loads successfully
- bad account reference fails
- bad contribution dates fail
- min/max conversion conflicts fail
- missing bridge account fails if referenced
Refine one schema detail before engine work
- the current cross-field validation treats all percent_of_salary contributions as employment-related and forces them to end before retirement
- that is fine for now, but if later you add non-employment percentage rules, it should be narrowed
Then build timeline_builder.py
- annual periods
- proration windows
- retirement transition
- age milestones
- start/stop events
Then build the projection engine in layers
- balances + contributions + expenses
- then taxes
- then mortgage
- then conversions
- then QCD/RMD/giving