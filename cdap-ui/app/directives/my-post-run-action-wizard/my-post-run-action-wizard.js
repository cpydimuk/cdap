/*
 * Copyright © 2015 Cask Data, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may not
 * use this file except in compliance with the License. You may obtain a copy of
 * the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations under
 * the License.
 */

angular.module(PKG.name + '.commons')
  .directive('myPostRunActionWizard', function() {
    return {
      scope: {
        mode: '@',
        actionCreator: '=?',
        store: '=',
        action: '=?',
        errors: '=',
      },
      templateUrl: 'my-post-run-action-wizard/my-post-run-action-wizard.html',
      bindToController: true,
      controller: 'MyPostRunActionWizardCtrl',
      controllerAs: 'MyPostRunActionWizardCtrl'
    };
  })
  .service('myPostRunActionWizardService', function($uibModal) {
    this.show = (actionCreator, store, mode, action) => {
      $uibModal.open({
        templateUrl: 'my-post-run-action-wizard/my-post-run-action-wizard-modal.html',
        backdrop: true,
        resolve: {
          rActionCreator: () => actionCreator || {},
          rStore: () => store,
          rAction: () => action || null,
          rMode: () => mode,
        },
        size: 'lg',
        windowClass: 'post-run-actions-modal hydrator-modal',
        controller: ['$scope', 'rActionCreator', 'rStore', 'rMode', 'rAction', function($scope, rActionCreator, rStore, rMode, rAction) {
          $scope.actionCreator = rActionCreator;
          $scope.store = rStore;
          $scope.mode = rMode;
          $scope.action = rAction;
          $scope.validating = false;
          $scope.showValidateButton = function() {
            // Hack-y way of showing Validate button on Configure and Confirm pages only
            if ($scope.action) {
              return $scope.mode !== 'view' && Object.keys($scope.action).length > 0;
            }
          };
          $scope.validatePluginProperties = function(){
            $scope.validating = true;
            const action = angular.copy($scope.action);
            const errorCb = ({ errorCount, propertyErrors }) => {
              $scope.validating = false;
              if ( errorCount > 0 || !errorCount) {
                $scope.propertyErrors = propertyErrors; 
              } else {
                $scope.propertyErrors = {};
              }
            };
            $scope.store.HydratorPlusPlusPluginConfigFactory.validatePluginProperties(action, errorCb);
            };
        }]
      });
    };
  });
