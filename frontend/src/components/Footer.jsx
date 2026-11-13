import React from 'react';

export default function Footer({ onNavigate }) {
  return (
    <footer className="bg-white border-t border-gray-200 py-4 px-6 text-xs text-gray-500">
      <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between space-y-2 sm:space-y-0">
        <p>
          &copy; {new Date().getFullYear()} Security Agency Business Management System. Karnataka, India.
        </p>
        <div className="flex items-center space-x-6">
          <button
            onClick={() => onNavigate('terms')}
            className="hover:text-gray-900 underline underline-offset-4"
          >
            Terms and Conditions
          </button>
          <button
            onClick={() => onNavigate('privacy')}
            className="hover:text-gray-900 underline underline-offset-4"
          >
            Privacy Policy
          </button>
        </div>
      </div>
    </footer>
  );
}

