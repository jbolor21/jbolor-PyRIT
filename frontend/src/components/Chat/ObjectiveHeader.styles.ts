import { makeStyles, tokens } from '@fluentui/react-components'

import {
  MINIMUM_TOUCH_TARGET_SIZE,
  NARROW_VIEWPORT_QUERY,
  TOUCH_INPUT_QUERY,
  mobileTouchTargetHeight,
} from '../../styles/touchTargets'

export const useObjectiveHeaderStyles = makeStyles({
  root: {
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'row',
    alignItems: 'baseline',
    columnGap: tokens.spacingHorizontalS,
    padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalL}`,
    backgroundColor: tokens.colorNeutralBackground2,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    borderLeft: `3px solid ${tokens.colorBrandStroke1}`,
    [NARROW_VIEWPORT_QUERY]: {
      alignItems: 'center',
      flexWrap: 'wrap',
      rowGap: tokens.spacingVerticalS,
      padding: `${tokens.spacingVerticalS} ${tokens.spacingHorizontalM}`,
    },
  },
  emptyRoot: {
    alignItems: 'center',
  },
  label: {
    flexShrink: 0,
  },
  outcomeSection: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalXS,
    flexShrink: 0,
    [NARROW_VIEWPORT_QUERY]: {
      flexBasis: '100%',
    },
  },
  separator: {
    alignSelf: 'stretch',
    borderLeft: `1px solid ${tokens.colorNeutralStroke2}`,
    [NARROW_VIEWPORT_QUERY]: {
      display: 'none',
    },
  },
  content: {
    flexGrow: 1,
    minWidth: 0,
    color: tokens.colorNeutralForeground1,
    fontSize: tokens.fontSizeBase300,
  },
  contentCollapsed: {
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  contentExpanded: {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    maxHeight: '30vh',
    overflowY: 'auto',
  },
  input: {
    flexGrow: 1,
    minWidth: 0,
    ...mobileTouchTargetHeight,
    '& input': {
      [TOUCH_INPUT_QUERY]: {
        minHeight: MINIMUM_TOUCH_TARGET_SIZE,
      },
    },
    [NARROW_VIEWPORT_QUERY]: {
      flexBasis: '100%',
      order: 2,
    },
  },
  addButton: {
    ...mobileTouchTargetHeight,
  },
  toggle: {
    flexShrink: 0,
    minWidth: 'auto',
    whiteSpace: 'nowrap',
    color: tokens.colorBrandForeground1,
    ...mobileTouchTargetHeight,
  },
  editorAction: {
    ...mobileTouchTargetHeight,
    [NARROW_VIEWPORT_QUERY]: {
      order: 3,
    },
  },
})
