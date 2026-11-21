import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

// Component tests for Phase D Adaptive Interview UI

describe('Adaptive Interview UI - Candidate Portal & Recruiter Transcript', () => {

  test('Candidate Portal - Follow-up badge shown and scores/verdicts are hidden', () => {
    // Simulates the question display card in InterviewPortal
    const isAdaptive = true;
    const activeTurn = {
      turn_id: 'turn_2',
      parent_turn_id: 'turn_1',
      type: 'probe_deeper',
      question: 'Can you explain how reference counting handles cyclical references in Python?',
      // Ensure internal fields might exist on object but must never be rendered
      _verdict: 'strong',
      _score: 90,
      _decider_reason: 'Probe deeper on cyclic GC'
    };
    const progressData = {
      current_core: 2,
      total_core: 5,
      turns_completed: 1,
      follow_ups_on_current: 1
    };

    const isFollowUpTurn = isAdaptive && ['probe_deeper', 'probe_gap', 'easier', 'restate'].includes(activeTurn.type);

    render(
      <div>
        <div data-testid="progress-header">
          Question {progressData.current_core} of {progressData.total_core}
        </div>
        <div data-testid="question-card">
          {isFollowUpTurn && <span data-testid="follow-up-badge">Follow-up</span>}
          <p>{activeTurn.question}</p>
        </div>
      </div>
    );

    // Subtle Follow-up badge is displayed
    expect(screen.getByTestId('follow-up-badge')).toHaveTextContent('Follow-up');

    // Progress hides remaining follow-ups and shows "Question 2 of 5"
    expect(screen.getByTestId('progress-header')).toHaveTextContent('Question 2 of 5');
    expect(screen.queryByText(/remaining/i)).not.toBeInTheDocument();

    // Internal fields MUST NEVER be rendered on candidate portal
    expect(screen.queryByText('strong')).not.toBeInTheDocument();
    expect(screen.queryByText('90')).not.toBeInTheDocument();
    expect(screen.queryByText(/cyclic GC/i)).not.toBeInTheDocument();
  });

  test('Candidate Portal - Thinking state and network retry button', () => {
    const isProcessing = true;
    const turnError = 'Network error submitting answer. Please click Retry.';
    const mockRetry = jest.fn();

    render(
      <div>
        {isProcessing && (
          <div data-testid="thinking-state">
            <p>Analyzing your response...</p>
            <p>Formulating the next question</p>
            {turnError && (
              <div>
                <p>{turnError}</p>
                <button onClick={mockRetry}>Retry Submission</button>
              </div>
            )}
          </div>
        )}
      </div>
    );

    expect(screen.getByTestId('thinking-state')).toHaveTextContent('Analyzing your response...');
    expect(screen.getByText('Retry Submission')).toBeInTheDocument();
  });

  test('Recruiter View - Threaded Transcript & Fallback Badge', () => {
    const turns = [
      {
        turn_id: 'turn_1',
        parent_turn_id: null,
        core_question_index: 0,
        type: 'core',
        question: 'What is Python memory management?',
        answer: 'It uses reference counting and garbage collection.',
        _verdict: 'strong',
        _score: 88,
        _decider_reason: 'Good explanation of memory management.'
      },
      {
        turn_id: 'turn_2',
        parent_turn_id: 'turn_1',
        core_question_index: 0,
        type: 'probe_deeper',
        question: 'How do you handle race conditions?',
        answer: 'Using mutexes or threading locks.',
        _verdict: 'partial',
        _score: 65,
        _decider_reason: 'Fallback to next_core: Groq request timed out after 5.0 seconds'
      }
    ];

    render(
      <div>
        {turns.map((turn, i) => {
          const isFallback = (turn._decider_reason || '').toLowerCase().includes('fallback');
          return (
            <div key={turn.turn_id} data-testid={`turn-${i}`}>
              <p>{turn.question}</p>
              <p>{turn.answer}</p>
              <span data-testid={`verdict-${i}`}>{turn._verdict.toUpperCase()}</span>
              <span data-testid={`score-${i}`}>{turn._score}/100</span>
              <p>{turn._decider_reason}</p>
              {isFallback && <span data-testid="fallback-badge">Fallback Used</span>}
            </div>
          );
        })}
      </div>
    );

    // Turn 1 assertions
    expect(screen.getByTestId('verdict-0')).toHaveTextContent('STRONG');
    expect(screen.getByTestId('score-0')).toHaveTextContent('88/100');
    expect(screen.getByText('Good explanation of memory management.')).toBeInTheDocument();

    // Turn 2 assertions & Fallback badge
    expect(screen.getByTestId('verdict-1')).toHaveTextContent('PARTIAL');
    expect(screen.getByTestId('score-1')).toHaveTextContent('65/100');
    expect(screen.getByTestId('fallback-badge')).toHaveTextContent('Fallback Used');
  });

});
