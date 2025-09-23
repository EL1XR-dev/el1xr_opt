import os
import pandas as pd
from   pyomo.environ     import Var, Reals, NonNegativeReals, Binary, UnitInterval

class AssetProcessor:
    def __init__(self, asset_type, model, data_frames, parameters_dict):
        self.asset_type = asset_type
        self.model = model
        self.data_frames = data_frames
        self.parameters_dict = parameters_dict
        self.prefix = f'p{asset_type}Gen'
        self.dem_prefix = f'p{asset_type}Dem'
        self.ret_prefix = f'p{asset_type}Ret'

    def process_assets(self):
        self._load_and_process_generation_data()
        self._calculate_costs()
        self._load_and_process_demand_data()
        self._load_and_process_retail_data()

    def _load_and_process_generation_data(self):
        generation_ind = self.data_frames[f'df{self.asset_type}Generation'].columns.to_list()
        idx_gen_factoring  = ['MaximumPower', 'MinimumPower', 'StandByPower', 'MaximumCharge', 'MinimumCharge', 'OMVariableCost', 'ProductionFunction', 'MaxCompressorConsumption',
                              'RampUp', 'RampDown', 'CO2EmissionRate', 'MaxOutflowsProd', 'MinOutflowsProd', 'MaxInflowsCons', 'MinInflowsCons', 'OutflowsRampDown', 'OutflowsRampUp']

        for idx in generation_ind:
            param_name = f'{self.prefix}{idx}'
            if idx in idx_gen_factoring:
                self.parameters_dict[param_name] = self.data_frames[f'df{self.asset_type}Generation'][idx] * self.model.factor1
            else:
                self.parameters_dict[param_name] = self.data_frames[f'df{self.asset_type}Generation'][idx]

    def _calculate_costs(self):
        self.parameters_dict[f'{self.prefix}LinearVarCost'] = self.parameters_dict[f'{self.prefix}LinearTerm'] * self.model.factor1 * self.parameters_dict[f'{self.prefix}FuelCost'] + self.parameters_dict[f'{self.prefix}OMVariableCost'] * self.model.factor1
        self.parameters_dict[f'{self.prefix}ConstantVarCost'] = self.parameters_dict[f'{self.prefix}ConstantTerm'] * self.model.factor2 * self.parameters_dict[f'{self.prefix}FuelCost']
        self.parameters_dict[f'{self.prefix}CO2EmissionCost'] = self.parameters_dict[f'{self.prefix}CO2EmissionRate'] * self.model.factor1 * self.parameters_dict['pParCO2Cost']
        self.parameters_dict[f'{self.prefix}StartUpCost'] = self.parameters_dict[f'{self.prefix}StartUpCost'] * self.model.factor2
        self.parameters_dict[f'{self.prefix}ShutDownCost'] = self.parameters_dict[f'{self.prefix}ShutDownCost'] * self.model.factor2
        self.parameters_dict[f'{self.prefix}InvestCost'] = self.parameters_dict[f'{self.prefix}FixedInvestmentCost'] * self.parameters_dict[f'{self.prefix}FixedChargeRate']
        self.parameters_dict[f'{self.prefix}RetireCost'] = self.parameters_dict[f'{self.prefix}FixedRetirementCost'] * self.parameters_dict[f'{self.prefix}FixedChargeRate']

    def _load_and_process_demand_data(self):
        demand_ind = self.data_frames[f'df{self.asset_type}Demand'].columns.to_list()
        idx_dem_factoring = ['MaximumPower']

        for idx in demand_ind:
            param_name = f'{self.dem_prefix}{idx}'
            if idx in idx_dem_factoring:
                self.parameters_dict[param_name] = self.data_frames[f'df{self.asset_type}Demand'][idx] * self.model.factor1
            else:
                self.parameters_dict[param_name] = self.data_frames[f'df{self.asset_type}Demand'][idx]

    def _load_and_process_retail_data(self):
        retail_ind = self.data_frames[f'df{self.asset_type}Retail'].columns.to_list()
        idx_retail_factoring = ['MaximumEnergyBuy', 'MinimumEnergyBuy', 'MaximumEnergySell', 'MinimumEnergySell']

        for idx in retail_ind:
            param_name = f'{self.ret_prefix}{idx}'
            if idx in idx_retail_factoring:
                self.parameters_dict[param_name] = self.data_frames[f'df{self.asset_type}Retail'][idx] * self.model.factor1
            else:
                self.parameters_dict[param_name] = self.data_frames[f'df{self.asset_type}Retail'][idx]

    def create_variables(self, optmodel):

        asset_type_lower = self.asset_type.lower()

        setattr(optmodel, f'v{self.asset_type}TotalOutput', Var(getattr(self.model, f'psn{asset_type_lower}g'), within=NonNegativeReals, doc=f'total {asset_type_lower} output of the unit'))
        setattr(optmodel, f'v{self.asset_type}TotalOutput2ndBlock', Var(getattr(self.model, f'psn{asset_type_lower}gnr'), within=NonNegativeReals, doc=f'second block of the unit'))
        setattr(optmodel, f'v{self.asset_type}TotalCharge', Var(getattr(self.model, f'psn{asset_type_lower}h'), within=NonNegativeReals, doc=f'ESS total charge power'))
        setattr(optmodel, f'v{self.asset_type}TotalCharge2ndBlock', Var(getattr(self.model, f'psn{asset_type_lower}h'), within=NonNegativeReals, doc=f'ESS charge power'))
        setattr(optmodel, f'v{self.asset_type}EnergyInflows', Var(getattr(self.model, f'psn{asset_type_lower}gs'), within=NonNegativeReals, doc=f'unscheduled inflows of all ESS units'))
        setattr(optmodel, f'v{self.asset_type}EnergyOutflows', Var(getattr(self.model, f'psn{asset_type_lower}gs'), within=NonNegativeReals, doc=f'scheduled outflows of all ESS units'))
        setattr(optmodel, f'v{self.asset_type}Inventory', Var(getattr(self.model, f'psn{asset_type_lower}gs'), within=NonNegativeReals, doc=f'ESS inventory'))
        setattr(optmodel, f'v{self.asset_type}Spillage', Var(getattr(self.model, f'psn{asset_type_lower}gs'), within=NonNegativeReals, doc=f'ESS spillage'))
        setattr(optmodel, f'v{self.asset_type}Buy', Var(getattr(self.model, f'psn{asset_type_lower}r'), within=NonNegativeReals, doc=f'energy buy'))
        setattr(optmodel, f'v{self.asset_type}Sell', Var(getattr(self.model, f'psn{asset_type_lower}r'), within=NonNegativeReals, doc=f'energy sell'))
        setattr(optmodel, f'v{self.asset_type}Demand', Var(getattr(self.model, f'psn{asset_type_lower}d'), within=NonNegativeReals, doc=f'{asset_type_lower} demand'))
        setattr(optmodel, f'v{self.asset_type}NS', Var(getattr(self.model, f'psn{asset_type_lower}d'), within=NonNegativeReals, doc=f'energy demand'))

        if self.model.Par['pOptIndBinGenOperat'] == 0:
            setattr(optmodel, f'v{self.asset_type}GenCommitment', Var(getattr(self.model, f'psn{asset_type_lower}gt'), within=UnitInterval, initialize=0, doc='generator binary commitment'))
            setattr(optmodel, f'v{self.asset_type}GenStartUp', Var(getattr(self.model, f'psn{asset_type_lower}gt'), within=UnitInterval, initialize=0, doc='generator binary start-up'))
            setattr(optmodel, f'v{self.asset_type}GenShutDown', Var(getattr(self.model, f'psn{asset_type_lower}gt'), within=UnitInterval, initialize=0, doc='generator binary shut-down'))
            setattr(optmodel, f'v{self.asset_type}StorOperat', Var(getattr(self.model, f'psn{asset_type_lower}gs'), within=UnitInterval, initialize=0, doc='storage binary operation'))
            setattr(optmodel, f'v{self.asset_type}PeakHourInd', Var(getattr(self.model, f'psn{asset_type_lower}r'), self.model.Peaks, within=UnitInterval, initialize=0, doc='peak hour indicator'))
        else:
            setattr(optmodel, f'v{self.asset_type}GenCommitment', Var(getattr(self.model, f'psn{asset_type_lower}gt'), within=Binary, initialize=0, doc='generator binary commitment'))
            setattr(optmodel, f'v{self.asset_type}GenStartUp', Var(getattr(self.model, f'psn{asset_type_lower}gt'), within=Binary, initialize=0, doc='generator binary start-up'))
            setattr(optmodel, f'v{self.asset_type}GenShutDown', Var(getattr(self.model, f'psn{asset_type_lower}gt'), within=Binary, initialize=0, doc='generator binary shut-down'))
            setattr(optmodel, f'v{self.asset_type}StorOperat', Var(getattr(self.model, f'psn{asset_type_lower}gs'), within=Binary, initialize=0, doc='storage binary operation'))
            setattr(optmodel, f'v{self.asset_type}PeakHourInd', Var(getattr(self.model, f'psn{asset_type_lower}r'), self.model.Peaks, within=Binary, initialize=0, doc='peak hour indicator'))

        if self.model.Par['pOptIndBinNetOperat'] == 0:
            setattr(optmodel, f'v{self.asset_type}NetCommit', Var(getattr(self.model, f'psn{asset_type_lower}la'), within=UnitInterval, initialize=0, doc='network binary operation'))
        else:
            setattr(optmodel, f'v{self.asset_type}NetCommit', Var(getattr(self.model, f'psn{asset_type_lower}la'), within=Binary, initialize=0, doc='network binary operation'))

        setattr(optmodel, f'v{self.asset_type}NetFlow', Var(getattr(self.model, f'psn{asset_type_lower}la'), within=Reals, doc=f'{asset_type_lower} net flow'))
        if self.asset_type == 'Ele':
            setattr(optmodel, 'vEleNetTheta', Var(self.model.psnnd, within=Reals, doc='electricity net theta'))
            if sum(self.model.Par['pEleDemFlexible'][idx] for idx in self.model.ed) > 0:
                setattr(optmodel, 'vEleDemFlex', Var(self.model.psned, within=Reals, doc='flexible electricity demand'))
