PAGE_MAPPING = {
#   '/_b_a_c_k_e_n_d/Insurance/insurance/': 'SIN-API-IF',
  '/_b_a_c_k_e_n_d/insurance/check_exists/': 'SIN-P-ICE',
  r'^/_b_a_c_k_e_n_d/Insurance/check_exists/?(\?.*)?$': 'SIN-API-OR',
  '/_b_a_c_k_e_n_d/Insurance/get_insurance_companies/': 'SIN-P-GIC',
  '/_b_a_c_k_e_n_d/Insurance/insurance/serve_file/<str:file_id>/': 'SIN-API-SF',
  '/_b_a_c_k_e_n_d/Insurance/insurance/update/.*/': 'SIN-API-FU',
#   r'^/_b_a_c_k_e_n_d/Insurance/insurance/update/?(\?.*)?$': 'SIN-API-FU',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/?(\?.*)?$': 'SIN-API-OR',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/report/?(\?.*)?$': 'SIN-API-OR',
  r'^/_b_a_c_k_e_n_d/Insurance/insurance/?(\?.*)?$': 'SIN-API-IF',
  


  'insurance/': 'SIN-API-IF',
  'check_exists/': 'SIN-P-ICE',
  'get_insurance_companies/': 'SIN-P-GIC',
  'insurance/serve_file/<str:file_id>/': 'SIN-API-SF',
  'insurance/update/': 'SIN-API-FU',
  'other_records/': 'SIN-API-OR',
  'other_records/report/': 'SIN-P-ORR'
}

PAGE_ACTION_MAPPING = {
    'xxx': {
        'DELETE':'RWD',
    },
}

GEN_ACTION_MAPPING = {
    'POST': 'RW',
    'PUT': 'RW',
    'DELETE': 'RW',
    'GET': 'R',
}