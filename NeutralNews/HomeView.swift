//
//  ContentView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 12/17/24.
//

import SwiftUI

struct HomeView: View {
    @State private var vm = ViewModel()
    
    var body: some View {
        NavigationStack {
            List {
                ForEach(vm.news) { new in
                    NavigationLink(destination: NewsView(news: vm.news)){
                        NewsRowView(news: new)
                    }
                }
            }
            .navigationTitle("Hoy")
        }
        .task {
            await vm.loadData()
        }
    }
}

#Preview {
    HomeView()
}
